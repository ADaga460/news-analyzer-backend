#main.py
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from newsanalyzer import analyze_url

app = FastAPI()

@app.post("/analyze")
async def analyze(request: Request):
    data = await request.json()
    url = data.get("url")
    if not url:
        return JSONResponse({"error": "Missing URL"}, status_code=400)
    result = analyze_url(url)
    return {"result": result}


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