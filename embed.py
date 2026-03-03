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
    result = supabase.rpc("match_program", {
        "query_embedding": query_embedding,
        "match_count": 5  # number of results to return
    }).execute().data or []

    # 4. Apply province filter
    if province_filter:
        result = [row for row in result if row.get("province") in province_filter]

    # 5. Fallback to organization if no programs found
    if not result:
        result = supabase.rpc("match_organization", {
            "query_embedding": query_embedding,
            "match_count": 5
        }).execute().data or []
        if province_filter:
            result = [row for row in result if row.get("province") in province_filter]

    # 6. Build structured JSON response
    response = []
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
    context_text = ""
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
    completion = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are an ecosystem assistant. Using provided data and information in links provided."},
            {"role": "user", "content": f"User question: {q.question}\n\nRelevant data:\n{context_text}"}
        ]
    )

    # Return chat-ready answer

    return {"answer": completion.choices[0].message.content}

