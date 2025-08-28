from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from newsanalyzer import analyze_url

# uvicorn server:app --reload --host 0.0.0.0 --port 8000

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/analyze")
async def analyze(url: str = Query(...)):
    result = analyze_url(url)
    return {"url": url, "result": result}

"""
{
  "version": 2,
  "builds": [
    { "src": "api/analyze.py", "use": "@vercel/python" }
  ],
  "routes": [
    { "src": "/analyze", "dest": "api/analyze.py" }
  ]
}

"""