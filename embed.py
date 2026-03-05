from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from openai import OpenAI
from supabase import create_client
from pydantic import BaseModel
import os

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

@app.get("/config")
def get_config():
    return {
        "supabase_url": os.environ.get("SUPABASE_URL"),
        "supabase_key": os.environ.get("SUPABASE_KEY"),
        "openai_key": os.environ.get("OPENAI_API_KEY")
    }

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
    province: str = None

def generate_embedding(text: str):
    response = openai_client.embeddings.create(
        model="text-embedding-3-small",
        input=text
    )
    return response.data[0].embedding

@app.get("/")
def serve_chat():
    return FileResponse("chat.html")

@app.post("/query")
def query_bot(q: Query):
    try:
        province_filter = province_expansion(q.province) if q.province else None
        query_embedding = generate_embedding(q.question)

        result = supabase.rpc("match_program", {
            "query_embedding": query_embedding,
            "match_count": 20
        }).execute().data or []

        if province_filter:
            result = [row for row in result if row.get("province") in province_filter]

        result = [row for row in result if row.get("similarity", 0) > 0.1]

        if not result:
            result = supabase.rpc("match_organization", {
                "query_embedding": query_embedding,
                "match_count": 20
            }).execute().data or []
            if province_filter:
                result = [row for row in result if row.get("province") in province_filter]
            result = [row for row in result if row.get("similarity", 0) > 0.1]

        if not result:
            return {"answer": "I couldn't find any relevant programs or organizations matching your question. Try rephrasing or selecting a different province."}

        context_text = ""
        for row in result:
            context_text += f"""
Program: {row.get('program')}
Program Description: {row.get('program_description')}
Organization: {row.get('organization_name')}
Organization Description: {row.get('org_description')}
Province: {row.get('province')}
Link: {row.get('program_link') or row.get('org_link')}
---
"""

        completion = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": """You are a helpful ecosystem assistant for Canadian innovation programs and organizations.
When answering:
- Be specific and reference the actual program/organization names from the data
- Include relevant links when available
- If the data doesn't perfectly match the question, mention the closest relevant programs
- Keep answers concise and friendly
- If no relevant data is found, say so clearly"""
                },
                {
                    "role": "user",
                    "content": f"User question: {q.question}\nProvince filter: {q.province or 'None'}\n\nRelevant data:\n{context_text}"
                }
            ]
        )

        return {"answer": completion.choices[0].message.content}

    except Exception as e:
        print(f"ERROR: {str(e)}")
        return {"answer": f"Backend error: {str(e)}"}


