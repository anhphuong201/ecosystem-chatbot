from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from openai import OpenAI
from supabase import create_client
import os

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

openai_client = OpenAI(api_key=OPENAI_API_KEY)
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Only this model is allowed through the chat proxy below, so the endpoint
# can't be used to run up costs on other OpenAI models.
ALLOWED_CHAT_MODEL = "gpt-4o-mini"
MAX_CHAT_TOKENS = 1200
MAX_MATCH_COUNT = 100

@app.get("/")
def serve_chat():
    return FileResponse("chat.html")

@app.head("/")
def head_root():
    return Response(status_code=200)

@app.api_route("/ping", methods=["GET", "HEAD"])
def ping():
    return {"status": "ok"}

@app.get("/favicon.ico")
def favicon():
    return FileResponse("static/favicon.ico")


# ─────────────────────────────────────────────
# OpenAI / Supabase proxy
# The browser never receives OPENAI_API_KEY or SUPABASE_KEY — every call to
# those services happens here, server-side, and only the result is returned.
# ─────────────────────────────────────────────

class EmbedRequest(BaseModel):
    text: str

@app.post("/api/embed")
def api_embed(body: EmbedRequest):
    try:
        resp = openai_client.embeddings.create(
            model="text-embedding-3-small", input=body.text
        )
    except Exception:
        raise HTTPException(status_code=502, detail="Embedding request failed")
    return {"embedding": resp.data[0].embedding}


class ChatRequest(BaseModel):
    model: str = ALLOWED_CHAT_MODEL
    messages: list
    response_format: dict | None = None
    max_tokens: int | None = None

@app.post("/api/chat")
def api_chat(body: ChatRequest):
    if body.model != ALLOWED_CHAT_MODEL:
        raise HTTPException(status_code=400, detail=f"Only '{ALLOWED_CHAT_MODEL}' is supported")

    kwargs = {"model": body.model, "messages": body.messages}
    if body.response_format is not None:
        kwargs["response_format"] = body.response_format
    if body.max_tokens is not None:
        kwargs["max_tokens"] = min(body.max_tokens, MAX_CHAT_TOKENS)

    try:
        resp = openai_client.chat.completions.create(**kwargs)
    except Exception:
        raise HTTPException(status_code=502, detail="Chat request failed")
    return {"content": resp.choices[0].message.content}


class SearchRequest(BaseModel):
    embedding: list[float]
    match_count: int = 50

@app.post("/api/search/programs")
def api_search_programs(body: SearchRequest):
    try:
        res = supabase.rpc("match_program", {
            "query_embedding": body.embedding,
            "match_count": min(body.match_count, MAX_MATCH_COUNT),
        }).execute()
    except Exception:
        raise HTTPException(status_code=502, detail="Program search failed")
    return {"data": res.data or []}

@app.post("/api/search/organizations")
def api_search_organizations(body: SearchRequest):
    try:
        res = supabase.rpc("match_organization", {
            "query_embedding": body.embedding,
            "match_count": min(body.match_count, MAX_MATCH_COUNT),
        }).execute()
    except Exception:
        raise HTTPException(status_code=502, detail="Organization search failed")
    return {"data": res.data or []}
