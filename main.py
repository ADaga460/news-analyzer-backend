from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from newsanalyzer import text
from gptreq import getRequests

app = FastAPI()

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

# 1) Extract raw article text
@app.post("/api/extract")
async def extract_article(request: Request):
    data = await request.json()
    url = data.get("url")
    if not url:
        return JSONResponse({"error": "Missing URL"}, status_code=400)
    
    try:
        article_text = text(url)
        if not article_text or article_text == "Could not retrieve article text.":
            return JSONResponse({"error": "Could not extract article text"}, status_code=500)
        return {"article_text": article_text}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

# 2) Analyze given article text with GPT
@app.post("/api/analyze-text")
async def analyze_text(request: Request):
    data = await request.json()
    article_text = data.get("text")
    if not article_text:
        return JSONResponse({"error": "Missing text"}, status_code=400)

    try:
        gpt_analysis = getRequests(article_text)
        return {"analysis": gpt_analysis}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
