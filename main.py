import os
import json
from typing import Dict
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import requests

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Hello from FastAPI Backend!"}

@app.get("/api/hello")
def hello():
    return {"message": "Hello from the backend API!"}

@app.get("/test")
def test_database():
    """Test endpoint to check if database is available and accessible"""
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    
    try:
        # Try to import database module
        from database import db
        
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            
            # Try to list collections to verify connectivity
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]  # Show first 10 collections
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
            
    except ImportError:
        response["database"] = "❌ Database module not found (run enable-database first)"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"
    
    # Check environment variables
    import os
    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
    
    return response


# ------------------------ QUIZ (Gemini w/ Safe Fallback) ------------------------

def _fallback_question() -> Dict[str, str]:
    """Return a deterministic, mid-level quiz when Gemini is unavailable.
    Kept simple to avoid leaking internal details and to ensure reliability."""
    pool = [
        {
            "prompt": "If f(x) = 2x^2 - 3x + 1, what is f(3)?",
            "solution": "10"
        },
        {
            "prompt": "Which planet has the strongest surface gravity among Earth, Mars, and Jupiter?",
            "solution": "Jupiter"
        },
        {
            "prompt": "Who wrote the play 'Hamlet'?",
            "solution": "William Shakespeare"
        },
        {
            "prompt": "In chemistry, what is the pH of a neutral solution at 25°C?",
            "solution": "7"
        },
        {
            "prompt": "What is the Big-O time complexity of binary search on a sorted array?",
            "solution": "O(log n)"
        },
    ]
    # Pseudo-random selection without importing random to keep surface small
    idx = (len(os.getenv("HOSTNAME", "x")) + len(os.getenv("PORT", "0"))) % len(pool)
    return pool[idx]

@app.get("/quiz")
def get_quiz():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return _fallback_question()

    try:
        url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent"
        headers = {"Content-Type": "application/json"}
        system_prompt = (
            "Generate one mid-level trivia question suitable for two teams playing locally. "
            "Output strictly as compact JSON with keys 'prompt' and 'solution'. "
            "Avoid code blocks or extra commentary."
        )
        body = {
            "contents": [
                {"parts": [{"text": system_prompt}]}
            ]
        }
        resp = requests.post(url, headers=headers, params={"key": api_key}, data=json.dumps(body), timeout=10)
        resp.raise_for_status()
        data = resp.json()
        # Extract text response safely
        text = None
        try:
            text = data["candidates"][0]["content"]["parts"][0]["text"]
        except Exception:
            text = None
        if not text:
            return _fallback_question()
        # Ensure we parse JSON even if model wrapped it in code fences
        text_stripped = text.strip().strip('`')
        # Find first { ... }
        start = text_stripped.find('{')
        end = text_stripped.rfind('}')
        if start == -1 or end == -1:
            return _fallback_question()
        json_str = text_stripped[start:end+1]
        obj = json.loads(json_str)
        prompt = str(obj.get("prompt", "")).strip()
        solution = str(obj.get("solution", "")).strip()
        if not prompt or not solution:
            return _fallback_question()
        # Basic output length limits to mitigate prompt injection/overlong payloads
        prompt = prompt[:300]
        solution = solution[:100]
        return {"prompt": prompt, "solution": solution}
    except Exception:
        # Never leak internal errors to client
        return _fallback_question()


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
