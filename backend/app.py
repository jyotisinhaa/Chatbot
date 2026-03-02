import os
from typing import List, Optional, Dict
import json
import uuid

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from openai import OpenAI
from pydantic import BaseModel

load_dotenv()

app = FastAPI(title="Chatbot UI API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory session storage for full conversation history
sessions: Dict[str, List[dict]] = {}


@app.get("/health")
def health():
    return {"status": "ok"}


class ChatRequest(BaseModel):
    model: str
    message: str  # Just the new user message
    session_id: Optional[str] = None
    api_key: Optional[str] = None
    max_tokens: int = 250
    temperature: float = 0.7


class ChatResponse(BaseModel):
    reply: str
    session_id: str


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    with open("frontend/index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())


@app.get("/static/{file_path:path}")
async def static_files(file_path: str):
    full_path = os.path.join("frontend", file_path)
    if os.path.exists(full_path):
        return FileResponse(full_path)
    raise HTTPException(status_code=404, detail="File not found")


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    if not request.api_key or not request.api_key.strip():
        raise HTTPException(status_code=400, detail="API key is required. Please provide a valid Groq API key.")

    api_key = request.api_key.strip()
    
    # Create or retrieve session
    session_id = request.session_id or str(uuid.uuid4())
    
    # Initialize session with system message if new
    if session_id not in sessions:
        sessions[session_id] = [
            {"role": "system", "content": "You are a helpful assistant. Keep responses concise."}
        ]
    
    # Add new user message to session history
    sessions[session_id].append({"role": "user", "content": request.message})
    
    # Use ALL messages from session as context (full conversation history)
    messages_to_send = sessions[session_id]

    print(f"DEBUG: Session ID: {session_id}")
    print(f"DEBUG: Using API key (last 10 chars): ...{api_key[-10:]}")
    print(f"DEBUG: Model: {request.model}")
    print(f"DEBUG: Full context size: {len(messages_to_send)} messages")

    client = OpenAI(
        base_url="https://api.groq.com/openai/v1",
        api_key=api_key,
    )

    try:
        completion = client.chat.completions.create(
            model=request.model,
            messages=messages_to_send,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    reply = completion.choices[0].message.content or ""
    
    # Add assistant response to session history
    sessions[session_id].append({"role": "assistant", "content": reply})
    
    return ChatResponse(reply=reply, session_id=session_id)