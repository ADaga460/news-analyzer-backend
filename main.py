#main.py
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from newsanalyzer import analyze_url

app = FastAPI()

@app.post("/api/analyze")
async def analyze(request: Request):
    print("start", flush=True)
    data = await request.json()
    url = data.get("url")
    if not url:
        print("fail", flush=True)
        return JSONResponse({"error": "Missing URL"}, status_code=400)
    print("pass 1", flush=True)
    result = analyze_url(url)
    return {"result": result}

from fastapi.middleware.cors import CORSMiddleware


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
"""
curl -X POST "http://127.0.0.1:8000/api/analyze" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.nytimes.com/2025/09/07/world/asia/japan-shigeru-ishiba-resign.html"}'

"""