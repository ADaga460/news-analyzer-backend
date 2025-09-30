# main.py
import uuid
from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from db import init_db, create_job, set_job_result, get_job
from newsanalyzer import text, extract_text_from_html, get_html_with_scraperapi
from gptreq import getRequests

import os

app = FastAPI()
init_db()

origins = [
    "https://news-analyzer-frontend-plat.vercel.app",
    "http://localhost:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# helper background worker for extraction
def _bg_extract(job_id: str, url: str):
    try:
        # First attempt: call text() which does fast GET & extraction
        extracted = text(url)

        # If remote blocked, try ScraperAPI fallback (inside background)
        if extracted == "BLOCKED_BY_REMOTE_SERVER":
            html = get_html_with_scraperapi(url)
            if html:
                extracted = extract_text_from_html(html, url)
            else:
                extracted = "Error: remote server blocked direct fetch and no SCRAPER_KEY provided."

        if not extracted:
            set_job_result(job_id, "failed", "Could not extract article text.")
        else:
            set_job_result(job_id, "done", extracted)
    except Exception as e:
        set_job_result(job_id, "failed", f"Extraction exception: {e}")

# helper background worker for analysis
def _bg_analyze(job_id: str, article_text: str):
    try:
        gpt_out = getRequests(article_text)
        set_job_result(job_id, "done", gpt_out)
    except Exception as e:
        set_job_result(job_id, "failed", f"LLM exception: {e}")

@app.post("/api/extract")
async def extract_article(request: Request, background_tasks: BackgroundTasks):
    data = await request.json()
    url = data.get("url")
    if not url:
        return JSONResponse({"error": "Missing URL"}, status_code=400)

    job_id = str(uuid.uuid4())
    create_job(job_id, "extract")
    # schedule background extraction
    background_tasks.add_task(_bg_extract, job_id, url)
    return {"job_id": job_id, "status": "processing"}

@app.post("/api/analyze-text")
async def analyze_text(request: Request, background_tasks: BackgroundTasks):
    data = await request.json()
    article_text = data.get("text")
    if not article_text:
        return JSONResponse({"error": "Missing text"}, status_code=400)

    job_id = str(uuid.uuid4())
    create_job(job_id, "analyze")
    background_tasks.add_task(_bg_analyze, job_id, article_text)
    return {"job_id": job_id, "status": "processing"}

@app.get("/api/job/{job_id}")
async def get_job_status(job_id: str):
    job = get_job(job_id)
    if not job:
        return JSONResponse({"error": "unknown job"}, status_code=404)
    return {"id": job["id"], "type": job["type"], "status": job["status"], "result": job["result"]}
