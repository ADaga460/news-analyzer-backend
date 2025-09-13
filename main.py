#main.py
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from newsanalyzer import analyze_url
from fastapi.middleware.cors import CORSMiddleware

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


"""
uvicorn server:app --reload --host 0.0.0.0 --port 8000

curl -X POST "http://127.0.0.1:8000/api/analyze" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.foxnews.com/media/boston-university-college-republicans-call-security-accountability-after-charlie-kirk-assassination"}'

"""