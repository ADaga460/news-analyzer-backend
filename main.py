# main.py
import uuid
import time # Import time for logging timestamps
from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import logging # Import logging

from db import init_db, create_job, set_job_result, get_job
from newsanalyzer import text, extract_text_from_html, get_html_with_scraperapi
from gptreq import getRequests

import os

# --- LOGGING SETUP ---
# Configure logging to stdout so Render can capture it
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

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
    start_time = time.time() # Add logging timestamp
    logging.info(f"[Worker:{job_id}] Starting extraction for URL: {url}")
    try:
        # First attempt: call text() which does fast GET & extraction
        extracted = text(url)
        logging.info(f"[Worker:{job_id}] Initial extraction result length: {len(extracted)}")

        # If remote blocked, try ScraperAPI fallback (inside background)
        if extracted == "BLOCKED_BY_REMOTE_SERVER":
            logging.info(f"[Worker:{job_id}] Remote blocked. Falling back to ScraperAPI.")
            html = get_html_with_scraperapi(url)
            if html:
                extracted = extract_text_from_html(html, url)
                logging.info(f"[Worker:{job_id}] ScraperAPI extraction length: {len(extracted)}")
            else:
                extracted = "Error: remote server blocked direct fetch and no SCRAPER_KEY provided."
                logging.warning(f"[Worker:{job_id}] ScraperAPI failed or key missing.")

        if not extracted or extracted == "Could not retrieve article text.":
            set_job_result(job_id, "failed", "Could not extract article text.")
            logging.error(f"[Worker:{job_id}] Failed to extract text.")
        else:
            set_job_result(job_id, "done", extracted)
            end_time = time.time()
            logging.info(f"[Worker:{job_id}] Extraction complete (Status: done). Took {end_time - start_time:.2f}s")
    except Exception as e:
        set_job_result(job_id, "failed", f"Extraction exception: {e}")
        logging.error(f"[Worker:{job_id}] Extraction failed with exception: {e}", exc_info=True)


# helper background worker for analysis
def _bg_analyze(job_id: str, article_text: str):
    start_time = time.time() # Add logging timestamp
    logging.info(f"[Worker:{job_id}] Starting analysis for text length: {len(article_text)}")
    try:
        gpt_out = getRequests(article_text)
        set_job_result(job_id, "done", gpt_out)
        end_time = time.time()
        logging.info(f"[Worker:{job_id}] Analysis complete (Status: done). Took {end_time - start_time:.2f}s")
    except Exception as e:
        set_job_result(job_id, "failed", f"LLM exception: {e}")
        logging.error(f"[Worker:{job_id}] Analysis failed with exception: {e}", exc_info=True)


@app.post("/api/extract")
async def extract_article(request: Request, background_tasks: BackgroundTasks):
    data = await request.json()
    url = data.get("url")
    if not url:
        logging.warning("[API:Extract] Received request with missing URL.")
        return JSONResponse({"error": "Missing URL"}, status_code=400)

    job_id = str(uuid.uuid4())
    create_job(job_id, "extract")
    
    # schedule background extraction
    background_tasks.add_task(_bg_extract, job_id, url)
    
    logging.info(f"[API:Extract] Enqueued job ID: {job_id} for URL: {url}")
    # This response is sent *immediately*
    return {"job_id": job_id, "status": "processing"}


@app.post("/api/analyze-text")
async def analyze_text(request: Request, background_tasks: BackgroundTasks):
    data = await request.json()
    text = data.get("text")
    text_len = len(text.strip()) if text else 0
    
    if not text or text_len < 500:
        logging.warning(f"[API:Analyze] Received request with invalid text length: {text_len}")
        return JSONResponse({"error": "Invalid or empty article text"}, status_code=400)

    job_id = str(uuid.uuid4())
    create_job(job_id, "analyze")
    background_tasks.add_task(_bg_analyze, job_id, text)
    
    logging.info(f"[API:Analyze] Enqueued job ID: {job_id} for text length: {text_len}")
    return {"job_id": job_id, "status": "processing"}


@app.get("/api/job/{job_id}")
async def get_job_status(job_id: str):
    job = get_job(job_id)
    if not job:
        logging.warning(f"[API:JobStatus] Requested unknown job ID: {job_id}")
        return JSONResponse({"error": "unknown job"}, status_code=404)
    
    logging.info(f"[API:JobStatus] Returning status for {job_id}: {job['status']}")
    return {"id": job["id"], "type": job["type"], "status": job["status"], "result": job["result"]}

# End of main.py