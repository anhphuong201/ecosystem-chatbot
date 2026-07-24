import os
from openai import OpenAI
from supabase import create_client

# ---------------- CONFIG ----------------
# Read from the environment -- never hardcode real keys here, this file is
# tracked in git.
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

if not OPENAI_API_KEY or not SUPABASE_URL or not SUPABASE_KEY:
    raise SystemExit(
        "Missing OPENAI_API_KEY / SUPABASE_URL / SUPABASE_KEY environment variables. "
        "Set them in your shell before running this script."
    )

openai_client = OpenAI(api_key=OPENAI_API_KEY)
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# -------------- EMBEDDING FUNCTION --------------
def generate_embedding(text: str):
    response = openai_client.embeddings.create(
        model="text-embedding-3-small",  # MUST MATCH 1536
        input=text
    )
    return response.data[0].embedding


# -------------- ORGANIZATIONS --------------
orgs = supabase.table("organization").select("*").execute().data

for org in orgs:
    text = " ".join(filter(None, [
        org.get('organization_name', ''),
        org.get('description', ''),
        org.get('search_summary', ''),
        org.get('province', ''),
        org.get('ecosystem', '')
    ]))
    embedding = generate_embedding(text)
    supabase.table("organization").update({
        "embedding": embedding
    }).eq("code", org["code"]).execute()
    print("Updated org:", org["organization_name"])


# -------------- PROGRAMS --------------
programs = supabase.table("program").select("*").execute().data

for prog in programs:
    text = " ".join(filter(None, [
        prog.get('program', ''),
        prog.get('description', ''),
        prog.get('search_summary', ''),
        prog.get('organization_name', ''),
        prog.get('industry', ''),
        prog.get('research_cluster', ''),
        prog.get('province', ''),
        prog.get('ecosystem', '')
    ]))
    embedding = generate_embedding(text)
    supabase.table("program").update({
        "embedding": embedding
    }).eq("id", prog["id"]).execute()
    print("Updated program:", prog["program"])

print("Done.")
