import os
import json
import sqlite3
import httpx
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, Request, Query
from fastapi.responses import StreamingResponse
from typing import Optional, AsyncGenerator

import logging
from .profile_scope import resolve_profile_scope

router = APIRouter()
logger = logging.getLogger("hermes.chat")

# Hermes API Server (default) - Use 127.0.0.1 to avoid Windows IPv6 resolution issues
HERMES_SERVER_URL = "http://127.0.0.1:8642/v1/chat/completions"

def get_db_path(profile: Optional[str] = None) -> Path:
    _, hermes_dir = resolve_profile_scope(profile)
    return Path(hermes_dir) / "state.db"

def get_api_key(profile: Optional[str] = None) -> Optional[str]:
    # Try environment first
    key = os.environ.get("OPENAI_API_KEY")
    if key:
        return key
    
    # Try .env in profile directory or home
    _, hermes_dir = resolve_profile_scope(profile)
    env_path = Path(hermes_dir) / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith("OPENAI_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    
    return None

@router.get("/chat/sessions")
async def list_chat_sessions(profile: str | None = None):
    """List recent chat sessions from state.db."""
    db_path = get_db_path(profile)
    if not db_path.exists():
        return {"sessions": []}

    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Only get sessions that have messages
        cursor.execute("""
            SELECT s.id, s.title, s.started_at, COUNT(m.id) as msg_count
            FROM sessions s
            JOIN messages m ON m.session_id = s.id
            GROUP BY s.id
            ORDER BY s.started_at DESC
            LIMIT 20
        """)
        
        sessions = []
        for row in cursor.fetchall():
            sessions.append({
                "id": row["id"],
                "title": row["title"] or "Untitled Session",
                "started_at": row["started_at"],
                "msg_count": row["msg_count"]
            })
        
        conn.close()
        return {"sessions": sessions}
    except Exception as e:
        return {"sessions": [], "error": str(e)}

@router.get("/chat/history")
async def get_chat_history(session_id: str, profile: str | None = None):
    """Get message history for a specific session."""
    db_path = get_db_path(profile)
    if not db_path.exists():
        return {"messages": []}

    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT role, content, timestamp
            FROM messages
            WHERE session_id = ?
            ORDER BY timestamp ASC
        """, (session_id,))
        
        messages = []
        for row in cursor.fetchall():
            messages.append({
                "role": row["role"],
                "content": row["content"],
                "timestamp": row["timestamp"]
            })
        
        conn.close()
        return {"messages": messages}
    except Exception as e:
        return {"messages": [], "error": str(e)}

@router.post("/chat/chat")
async def chat_completions(request: Request, profile: str | None = None):
    """Bridge to Hermes API Server with streaming support."""
    body = await request.json()
    api_key = get_api_key(profile)
    
    logger.info(f"Chat request for profile: {profile}")
    
    # We strip profile from body before forwarding if it was sent there
    if "profile" in body:
        del body["profile"]

    headers = {
        "Content-Type": "application/json",
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    async def stream_response() -> AsyncGenerator[str, None]:
        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                logger.info(f"Connecting to Hermes API at {HERMES_SERVER_URL}")
                async with client.stream("POST", HERMES_SERVER_URL, json=body, headers=headers) as response:
                    logger.info(f"Hermes API Response Status: {response.status_code}")
                    async for line in response.aiter_lines():
                        if line:
                            yield f"{line}\n\n"
            except Exception as e:
                logger.error(f"Stream error: {str(e)}")
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
                yield "data: [DONE]\n\n"

    return StreamingResponse(stream_response(), media_type="text/event-stream")
