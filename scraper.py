import os
import time
import json
import requests
from bs4 import BeautifulSoup
from openai import OpenAI
from supabase import create_client

# Don't initialize clients at top level
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

def get_clients():
    if not OPENAI_API_KEY or not SUPABASE_URL or not SUPABASE_KEY:
        raise ValueError("Missing required environment variables")
    openai_client = OpenAI(api_key=OPENAI_API_KEY)
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    return openai_client, supabase

def scrape_website(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")
        for tag in soup(["nav", "footer", "script", "style", "header"]):
            tag.decompose()
        text = soup.get_text(separator=" ", strip=True)
        return text[:3000]
    except Exception as e:
        print(f"Failed to scrape {url}: {e}")
        return None

def generate_summary(openai_client, org_name, scraped_text):
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": """You are helping build a search index for Atlantic Canada innovation ecosystem.
Given scraped website content, generate:
1. A concise 2-3 sentence description of what this organization/program does
2. A search_summary with key topics, industries, services, and keywords

Respond in JSON format only:
{
  "description": "...",
  "search_summary": "..."
}"""
                },
                {
                    "role": "user",
                    "content": f"Organization: {org_name}\n\nWebsite content:\n{scraped_text}"
                }
            ]
        )
        content = response.choices[0].message.content
        content = content.replace("```json", "").replace("```", "").strip()
        return json.loads(content)
    except Exception as e:
        print(f"Failed to generate summary for {org_name}: {e}")
        return None

def generate_embedding(openai_client, text):
    response = openai_client.embeddings.create(
        model="text-embedding-3-small",
        input=text
    )
    return response.data[0].embedding

def update_organizations(openai_client, supabase):
    orgs = supabase.table("organization").select("*").execute().data
    print(f"Updating {len(orgs)} organizations...")

    for org in orgs:
        url = org.get("link")
        if not url:
            print(f"Skipping {org['organization_name']} - no URL")
            continue

        print(f"Scraping: {org['organization_name']} - {url}")
        scraped = scrape_website(url)
        if not scraped:
            continue

        summary = generate_summary(openai_client, org['organization_name'], scraped)
        if not summary:
            continue

        embedding_text = f"{org['organization_name']} {summary['description']} {summary['search_summary']} {org.get('province', '')}"
        embedding = generate_embedding(openai_client, embedding_text)

        supabase.table("organization").update({
            "description": summary["description"],
            "search_summary": summary["search_summary"],
            "embedding": embedding
        }).eq("code", org["code"]).execute()

        print(f"Updated: {org['organization_name']}")
        time.sleep(1)

def update_programs(openai_client, supabase):
    programs = supabase.table("program").select("*").execute().data
    print(f"Updating {len(programs)} programs...")

    for prog in programs:
        url = prog.get("link")
        if not url:
            print(f"Skipping {prog['program']} - no URL")
            continue

        print(f"Scraping: {prog['program']} - {url}")
        scraped = scrape_website(url)
        if not scraped:
            continue

        summary = generate_summary(openai_client, prog['program'], scraped)
        if not summary:
            continue

        embedding_text = " ".join(filter(None, [
            prog.get('program', ''),
            summary['description'],
            summary['search_summary'],
            prog.get('organization_name', ''),
            prog.get('industry', ''),
            prog.get('research_cluster', ''),
            prog.get('province', ''),
            prog.get('ecosystem', '')
        ]))
        embedding = generate_embedding(openai_client, embedding_text)

        supabase.table("program").update({
            "description": summary["description"],
            "search_summary": summary["search_summary"],
            "embedding": embedding
        }).eq("id", prog["id"]).execute()

        print(f"Updated: {prog['program']}")
        time.sleep(1)

if __name__ == "__main__":
    print("Starting scraper...")
    openai_client, supabase = get_clients()
    update_organizations(openai_client, supabase)
    update_programs(openai_client, supabase)
    print("Done!")
