from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from openai import OpenAI
from supabase import create_client
import os
import re
import time

app = FastAPI()

# Whole-sector listings can be a few hundred rows of text; compress them.
app.add_middleware(GZipMiddleware, minimum_size=1000)

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

# The program table is a few hundred rows that change rarely, so the sector
# browse below keeps a short-lived in-memory copy instead of re-reading it
# on every question. Uploads show up within PROGRAM_CACHE_SECONDS.
PROGRAM_CACHE_SECONDS = 300
PROGRAM_COLUMNS = (
    "program,description,search_summary,organization_name,province,link,"
    "industry,ecosystem,research_cluster"
)
MAX_BROWSE_KEYWORDS = 12
MAX_KEYWORD_LENGTH = 60
_program_cache = {"at": 0.0, "rows": []}

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


# ─────────────────────────────────────────────
# Whole-sector browse
# Vector search only returns the nearest matches, so it can't list *everything*
# in a sector (e.g. all ~90 Defense & Aerospace programs). This returns every
# program tagged with the sector, plus any untagged program whose text
# literally mentions one of the sector's keywords.
# ─────────────────────────────────────────────

def load_programs():
    now = time.time()
    if _program_cache["rows"] and now - _program_cache["at"] < PROGRAM_CACHE_SECONDS:
        return _program_cache["rows"]

    rows, start, page = [], 0, 1000
    while True:
        batch = (
            supabase.table("program")
            .select(PROGRAM_COLUMNS)
            .range(start, start + page - 1)
            .execute()
            .data
            or []
        )
        rows.extend(batch)
        if len(batch) < page:
            break
        start += page

    _program_cache["rows"] = rows
    _program_cache["at"] = now
    return rows


class BrowseRequest(BaseModel):
    industry: str | None = None
    keywords: list[str] = []
    # Only programs whose organization name contains this. Combined with
    # industry/keywords when those are given, otherwise returns all of the
    # organization's programs.
    organization: str | None = None

@app.post("/api/programs/browse")
def api_browse_programs(body: BrowseRequest):
    tag = (body.industry or "").strip().lower()
    organization = (body.organization or "").strip().lower()[:MAX_KEYWORD_LENGTH * 2]
    keywords = [
        k.strip()[:MAX_KEYWORD_LENGTH]
        for k in body.keywords[:MAX_BROWSE_KEYWORDS]
        if k.strip()
    ]
    if not tag and not keywords and not organization:
        raise HTTPException(status_code=400, detail="industry, keywords or organization required")

    pattern = (
        re.compile(r"\b(?:" + "|".join(re.escape(k) for k in keywords) + r")\b", re.IGNORECASE)
        if keywords else None
    )

    try:
        rows = load_programs()
    except Exception:
        raise HTTPException(status_code=502, detail="Program browse failed")

    matches = []
    for r in rows:
        if organization and organization not in (r.get("organization_name") or "").lower():
            continue
        tags = {t.strip().lower() for t in (r.get("industry") or "").split(",")}
        text = " ".join(filter(None, [r.get("program"), r.get("description"), r.get("search_summary")]))
        topic_match = (tag and tag in tags) or (pattern and pattern.search(text))
        if topic_match or (organization and not tag and not pattern):
            # Same shape the vector search returns, plus the sector tags.
            matches.append({
                "program": r.get("program"),
                "program_description": r.get("description"),
                "organization_name": r.get("organization_name"),
                "org_description": None,
                "province": r.get("province"),
                "program_link": r.get("link"),
                "org_link": None,
                "industry": r.get("industry"),
                "ecosystem": r.get("ecosystem"),
                "research_cluster": r.get("research_cluster"),
                "similarity": None,
            })
    return {"data": matches}
