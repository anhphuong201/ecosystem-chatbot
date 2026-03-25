from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.responses import JSONResponse
from flask import Flask, send_from_directory
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

@app.get("/")
def serve_chat():
    return FileResponse("chat.html")

@app.get("/config")
def get_config():
    return {
        "supabase_url": SUPABASE_URL,
        "supabase_key": SUPABASE_KEY,
        "openai_key": OPENAI_API_KEY
    }

@app.api_route("/health", methods=["GET", "HEAD"])
def health():
    return JSONResponse({"status": "ok"})

app = Flask(__name__)

@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory('static', filename)
