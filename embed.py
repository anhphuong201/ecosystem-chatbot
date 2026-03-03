import os
from openai import OpenAI
from supabase import create_client
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

# Keys
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

openai_client = OpenAI(api_key=OPENAI_API_KEY)
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


ATLANTIC_PROVINCES = ["NS", "NL", "PE", "NB"]

def province_expansion(province: str):
    if province == "Atlantic Canada":
        return ATLANTIC_PROVINCES + ["Atlantic Canada"]
    if province in ATLANTIC_PROVINCES:
        return [province, "Atlantic Canada"]
    return [province]

class Query(BaseModel):
    question: str
    province: str = None  # optional province filter

# -----------------------------
# Helper function to generate embedding
# -----------------------------
# -------------- EMBEDDING FUNCTION --------------
def generate_embedding(text: str):
    response = openai_client.embeddings.create(
        model="text-embedding-3-small",  # MUST MATCH 1536
        input=text
    )
    return response.data[0].embedding

# -----------------------------
# Main endpoint
# -----------------------------
@app.post("/query")
def query_bot(q: Query):
    # 1. Expand province filter if provided
    province_filter = province_expansion(q.province) if q.province else None

    # 2. Embed user question
    query_embedding = generate_embedding(q.question)

    # 3. Semantic search in programs (vector search)
    # Supabase RPC function 'match_program' should be defined using vector search on program.embedding
        # Increase match_count before filtering
    result = supabase.rpc("match_program", {
        "query_embedding": query_embedding,
        "match_count": 20
    }).execute().data or []
    

    # 4. Apply province filter
    if province_filter:
        result = [row for row in result if row.get("province") in province_filter]

    # Filter by similarity threshold
    result = [row for row in result if row.get("similarity", 0) > 0.3]

    # 5. Fallback to organization if no programs found
    if not result:
        result = supabase.rpc("match_organization", {
            "query_embedding": query_embedding,
            "match_count": 20
        }).execute().data or []
        if province_filter:
            result = [row for row in result if row.get("province") in province_filter]
        result = [row for row in result if row.get("similarity", 0) > 0.3]
# Build context
    if not result:
        return {"answer": "I'm sorry, I couldn't find any relevant programs or organizations matching your question. Try rephrasing or selecting a different province."}
    
    context_text = ""
    response = []
    
    # 6. Build structured JSON response
    for row in result:
        response.append({
            "program_name": row.get("program"),
            "program_description": row.get("program_description"),
            "organization_name": row.get("organization_name"),
            "org_description": row.get("org_description"),
            "province": row.get("province"),
            "program_link": row.get("program_link"),
            "org_link": row.get("org_link")
        })

        # Build a single text block from results
    for r in response:
        context_text += f"""
    Program: {r.get('program_name')}
    Program Description: {r.get('program_description')}
    Organization: {r.get('organization_name')}
    Organization Description: {r.get('org_description')}
    Province: {r.get('province')}
    Link: {r.get('program_link') or r.get('org_link')}
    ---
    """

    # Generate a natural language answer using OpenAI
        # Improved prompt
    completion = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": """You are a helpful ecosystem assistant for Atlantic innovation ecosystem. You give advice about research labs, innovation programs and organizations.
When answering:
- Startups, spinoffs also means entrepreneurs.
- Be specific and reference the actual program/organization names from the data
- Include relevant links when available
- If the data doesn't perfectly match the question, mention the closest relevant programs
- Keep answers concise and friendly
- If no relevant data is found, say so clearly"""
            },
            {
                "role": "user",
                "content": f"""User question: {q.question}
Province filter: {q.province or 'None'}

Relevant programs and organizations found:
{context_text}

Please answer the user's question based on this data."""
            }
        ]
    )
    

    # Return chat-ready answer

    return {"answer": completion.choices[0].message.content}

# UI Html for chatbot
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

app.mount("/static", StaticFiles(directory="."), name="static")

@app.get("/")
def serve_chat():
    return FileResponse("chat.html")



