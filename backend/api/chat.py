import os
import json
import sqlite3
import httpx
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, AsyncGenerator, List, Dict
from fastapi import APIRouter, Request, Query
from fastapi.responses import StreamingResponse
from starlette.concurrency import run_in_threadpool

from .profile_scope import resolve_profile_scope

router = APIRouter()
logger = logging.getLogger("hermes.chat")

# Hermes API Server (default) - Use 127.0.0.1 to avoid Windows IPv6 resolution issues
HERMES_SERVER_URL = "http://127.0.0.1:8642/v1/chat/completions"

def get_db_path(profile: Optional[str] = None) -> Path:
    _, hermes_dir = resolve_profile_scope(profile)
    return Path(hermes_dir) / "state.db"

def get_api_key(profile: Optional[str] = None) -> Optional[str]:
    # Prioritize API_SERVER_KEY as requested
    key = os.environ.get("API_SERVER_KEY")
    if key:
        return key
    
    # Try .env in profile directory
    _, hermes_dir = resolve_profile_scope(profile)
    env_path = Path(hermes_dir) / ".env"
    
    if env_path.exists():
        try:
            content = env_path.read_text(encoding="utf-8")
            for line in content.splitlines():
                line = line.strip()
                if not line or line.startswith("#"): continue
                
                # Check for API_SERVER_KEY first
                if line.startswith("API_SERVER_KEY="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
                
                # Fallback to OPENAI_API_KEY if needed
                if line.startswith("OPENAI_API_KEY="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
        except Exception as e:
            logger.error(f"Error reading .env at {env_path}: {e}")
    
    return os.environ.get("OPENAI_API_KEY")

# --- Synchronous Helpers for Threadpool ---

def _get_history_sync(db_path: str, session_id: Optional[str] = None):
    """Synchronous helper for history."""
    conn = sqlite3.connect(db_path, timeout=5.0)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()
        if session_id:
            cur.execute("""
                SELECT role, content, created_at FROM messages 
                WHERE session_id = ? ORDER BY created_at ASC
            """, (session_id,))
        else:
            cur.execute("SELECT role, content, created_at FROM messages ORDER BY created_at ASC LIMIT 100")
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()

def _get_sessions_sync(db_path: str):
    """Synchronous helper for sessions."""
    conn = sqlite3.connect(db_path, timeout=5.0)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()
        # Only get sessions that have messages
        cur.execute("""
            SELECT s.id, s.title, s.started_at, COUNT(m.id) as msg_count
            FROM sessions s
            LEFT JOIN messages m ON m.session_id = s.id
            GROUP BY s.id
            ORDER BY s.started_at DESC
            LIMIT 50
        """)
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()

def _save_message_sync(db_path: str, session_id: str, role: str, content: str):
    """Synchronous helper to save messages."""
    conn = sqlite3.connect(db_path, timeout=5.0)
    try:
        cur = conn.cursor()
        # Ensure session exists (simple UPSERT or ignore)
        cur.execute("INSERT OR IGNORE INTO sessions (id, started_at) VALUES (?, ?)", (session_id, datetime.now().timestamp()))
        cur.execute("INSERT INTO messages (session_id, role, content, created_at) VALUES (?, ?, ?, ?)",
                    (session_id, role, content, datetime.now().timestamp()))
        conn.commit()
    finally:
        conn.close()

# --- Async API Endpoints ---

@router.get("/chat/sessions")
async def get_sessions(profile: str | None = None):
    db_path = get_db_path(profile)
    if not db_path.exists():
        return []
    try:
        return await run_in_threadpool(_get_sessions_sync, str(db_path))
    except Exception as e:
        logger.error(f"Error loading sessions: {e}")
        return []

@router.get("/chat/history")
async def get_history(session_id: str | None = None, profile: str | None = None):
    db_path = get_db_path(profile)
    if not db_path.exists():
        return []
    try:
        return await run_in_threadpool(_get_history_sync, str(db_path), session_id)
    except Exception as e:
        logger.error(f"Error loading history: {e}")
        return []

@router.post("/chat/chat")
async def chat_completions(request: Request, profile: str | None = None):
    """Bridge to Hermes API Server with streaming support."""
    try:
        body = await request.json()
    except:
        return {"error": "Invalid JSON body"}
        
    api_key = get_api_key(profile)
    session_id = body.get("session_id", "default")
    
    logger.info(f"[Chat] Request for profile: {profile}, session: {session_id}")
    
    # Strip non-standard fields for forwarding
    forward_body = {k: v for k, v in body.items() if k not in ("profile", "session_id")}

    headers = { "Content-Type": "application/json" }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    async def stream_response() -> AsyncGenerator[str, None]:
        full_assistant_message = ""
        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                logger.info(f"[Chat] Connecting to {HERMES_SERVER_URL}...")
                async with client.stream("POST", HERMES_SERVER_URL, json=forward_body, headers=headers) as response:
                    logger.info(f"[Chat] Hermes Response Status: {response.status_code}")
                    
                    if response.status_code != 200:
                        err_text = await response.aread()
                        logger.error(f"[Chat] Error from upstream: {err_text.decode()}")
                        yield f"data: {json.dumps({'error': 'Upstream error', 'details': err_text.decode()})}\n\n"
                        return

                    async for line in response.aiter_lines():
                        if not line: continue
                        yield f"{line}\n\n"
                        
                        # Extract content for saving to DB
                        if line.startswith("data: "):
                            data_str = line[6:]
                            if data_str == "[DONE]": break
                            try:
                                data = json.loads(data_str)
                                content = data.get("choices", [{}])[0].get("delta", {}).get("content", "")
                                if content: full_assistant_message += content
                            except: pass
                
                # Save assistant message to DB at the end
                if full_assistant_message:
                    db_path = get_db_path(profile)
                    await run_in_threadpool(_save_message_sync, str(db_path), session_id, "assistant", full_assistant_message)
                    logger.info(f"[Chat] Saved assistant response ({len(full_assistant_message)} chars)")

            except Exception as e:
                logger.error(f"[Chat] Stream exception: {str(e)}")
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
                yield "data: [DONE]\n\n"

    # Save user message to DB before starting stream
    user_msgs = [m for m in body.get("messages", []) if m.get("role") == "user"]
    if user_msgs:
        try:
            db_path = get_db_path(profile)
            await run_in_threadpool(_save_message_sync, str(db_path), session_id, "user", user_msgs[-1]["content"])
        except Exception as e:
            logger.error(f"Failed to save user message: {e}")

    return StreamingResponse(stream_response(), media_type="text/event-stream")
