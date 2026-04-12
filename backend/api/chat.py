"""API routes for Agent Chat feature."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..chat import (
    ChatEngine,
    ChatNotAvailableError,
    ChatSession,
    chat_engine,
)
from ..collectors.sessions import collect_sessions

router = APIRouter(prefix="/chat", tags=["chat"])


# Request/Response Models
class CreateSessionRequest(BaseModel):
    profile: str | None = None
    model: str | None = None


class SendMessageRequest(BaseModel):
    content: str


class SessionResponse(BaseModel):
    id: str
    profile: str | None
    model: str | None
    title: str
    backend_type: str
    is_active: bool
    message_count: int


class ComposerStateResponse(BaseModel):
    model: str
    is_streaming: bool
    context_tokens: int


@router.post("/sessions", response_model=SessionResponse)
async def create_session(request: CreateSessionRequest) -> SessionResponse:
    """Create a new chat session."""
    try:
        session = chat_engine.create_session(
            profile=request.profile, model=request.model
        )
        return SessionResponse(
            id=session.id,
            profile=session.profile,
            model=session.model,
            title=session.title,
            backend_type=session.backend_type,
            is_active=session.is_active,
            message_count=session.message_count,
        )
    except ChatNotAvailableError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/sessions", response_model=list[SessionResponse])
async def list_sessions() -> list[SessionResponse]:
    """List all active chat sessions."""
    sessions = chat_engine.list_sessions()
    return [
        SessionResponse(
            id=s.id,
            profile=s.profile,
            model=s.model,
            title=s.title,
            backend_type=s.backend_type,
            is_active=s.is_active,
            message_count=s.message_count,
        )
        for s in sessions
    ]


@router.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str) -> SessionResponse:
    """Get a specific session."""
    session = chat_engine.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return SessionResponse(
        id=session.id,
        profile=session.profile,
        model=session.model,
        title=session.title,
        backend_type=session.backend_type,
        is_active=session.is_active,
        message_count=session.message_count,
    )


@router.delete("/sessions/{session_id}")
async def end_session(session_id: str) -> dict[str, str]:
    """End a chat session."""
    if chat_engine.end_session(session_id):
        return {"status": "ended", "session_id": session_id}
    raise HTTPException(status_code=404, detail="Session not found")


@router.post("/sessions/{session_id}/send")
async def send_message(session_id: str, request: SendMessageRequest) -> dict[str, str]:
    """Send a message to a session."""
    session = chat_engine.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if not session.is_active:
        raise HTTPException(status_code=409, detail="Session is inactive")

    # Send message - this creates the streamer
    try:
        chat_engine.send_message(session_id, request.content)
        return {"status": "accepted", "session_id": session_id}
    except ChatNotAvailableError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions/{session_id}/stream")
async def stream_response(session_id: str) -> StreamingResponse:
    """Stream chat response via SSE."""
    session = chat_engine.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if not session.is_active:
        raise HTTPException(status_code=409, detail="Session is inactive")

    try:
        # This is called when user sends a message via POST first
        # The streamer was created during that call
        streamer = chat_engine._streamers.get(session_id)

        if not streamer:
            # No active stream, return error
            raise HTTPException(
                status_code=400, detail="No active message stream. Send message first."
            )

        def event_generator():
            """Generate SSE events."""
            for event in streamer.iter_events():
                yield streamer.to_sse(event)

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  # Disable nginx buffering
            },
        )

    except ChatNotAvailableError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/sessions/{session_id}/history")
async def get_history(session_id: str, limit: int = 50) -> list[dict[str, Any]]:
    """Get message history for a session from state.db."""
    # This reads from the existing sessions collector
    # We just need to filter by session_id
    sessions_state = collect_sessions()

    # Find session in database
    for session in sessions_state.recent_sessions:
        if session.session_id == session_id:
            # Get detailed messages from state.db
            # This would need a new collector to read messages table
            # For now, return placeholder
            return []

    return []


@router.get("/sessions/{session_id}/composer", response_model=ComposerStateResponse)
async def get_composer_state(session_id: str) -> ComposerStateResponse:
    """Get composer state for UI footer."""
    try:
        state = chat_engine.get_composer_state(session_id)
        return ComposerStateResponse(
            model=state.model,
            is_streaming=state.is_streaming,
            context_tokens=state.context_tokens,
        )
    except Exception as e:
        # Return default if session not found
        return ComposerStateResponse(
            model="unknown",
            is_streaming=False,
            context_tokens=0,
        )


@router.get("/available")
async def check_availability() -> dict[str, Any]:
    """Check if chat functionality is available."""
    from ..chat import TmuxChatFallback

    cli_available = chat_engine.is_available()

    direct_import = False
    try:
        from run_agent import AIAgent

        direct_import = True
    except ImportError:
        pass

    tmux_available = TmuxChatFallback.is_available()
    tmux_pane = TmuxChatFallback.find_hermes_pane() if tmux_available else None

    return {
        "available": cli_available or direct_import or (tmux_available and tmux_pane is not None),
        "cli_available": cli_available,
        "direct_import": direct_import,
        "tmux_available": tmux_available,
        "tmux_pane_found": tmux_pane is not None,
        "tmux_pane_id": tmux_pane,
    }
