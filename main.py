#main.py
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from newsanalyzer import analyze_url

app = FastAPI()

@app.post("/api/analyze")
async def analyze(request: Request):
    data = await request.json()
    url = data.get("url")
    if not url:
        return JSONResponse({"error": "Missing URL"}, status_code=400)
    result = analyze_url(url)
    return {"result": result}

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

origins = [
    "https://news-analyzer-frontend-plat.vercel.app",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
