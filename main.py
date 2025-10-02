# main.py
import uuid
import logging
from typing import Dict, Any
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import concurrent.futures

from newsanalyzer import text as extract_text_fn
from gptreq import getRequests

logger = logging.getLogger("uvicorn.error")

app = FastAPI()

# CORS: allow your frontend + local dev
FRONTEND_ORIGINS = [
    "https://news-analyzer-frontend-plat.vercel.app",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins= ["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Job storage
JOBS: Dict[str, Dict[str, Any]] = {}
EXECUTOR = concurrent.futures.ThreadPoolExecutor(max_workers=2)

def start_background(fn, job_id: str, *args, **kwargs):
    def _run():
        try:
            JOBS[job_id]["status"] = "running"
            result = fn(*args, **kwargs)
            JOBS[job_id]["status"] = "done"
            JOBS[job_id]["result"] = result
        except Exception as e:
            logger.exception("Job failed")
            JOBS[job_id]["status"] = "failed"
            JOBS[job_id]["result"] = f"Error: {e}"
    EXECUTOR.submit(_run)

@app.post("/api/extract")
async def extract_endpoint(request: Request):
    data = await request.json()
    url = data.get("url")
    if not url:
        return JSONResponse({"error": "Missing url"}, status_code=400)

    job_id = str(uuid.uuid4())
    JOBS[job_id] = {"status": "pending", "result": None, "type": "extract"}

    start_background(extract_text_fn, job_id, url)
    return {"job_id": job_id}

@app.post("/api/analyze-text")
async def analyze_text_endpoint(request: Request):
    data = await request.json()
    text_blob = data.get("text")
    if not text_blob or len(text_blob.strip()) < 20:
        return JSONResponse({"error": "Missing or too short text"}, status_code=400)

    job_id = str(uuid.uuid4())
    JOBS[job_id] = {"status": "pending", "result": None, "type": "analyze"}

    start_background(getRequests, job_id, text_blob)
    return {"job_id": job_id}

@app.get("/api/job/{job_id}")
async def get_job(job_id: str):
    info = JOBS.get(job_id)
    if not info:
        return JSONResponse({"error": "Job not found"}, status_code=404)
    return {"job_id": job_id, "status": info["status"], "result": info["result"]}

@app.get("/health")
async def health():
    return {"status": "ok"}
