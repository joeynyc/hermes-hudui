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
router = APIRouter(prefix="/chat", tags=["chat"])


# Request/Response Models
class CreateSessionRequest(BaseModel):
    profile: str | None = None
    model: str | None = None


class AISDKSendRequest(BaseModel):
    messages: list[dict]
    lang: str | None = None


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
    status: str = "idle"
    elapsed_ms: int = 0
    first_token_ms: int | None = None
    total_ms: int | None = None
    process_start_ms: int | None = None
    resumed: bool = False
    recent_first_token_avg_ms: int | None = None
    recent_total_avg_ms: int | None = None
    recent_runs: int = 0


@router.post("/sessions", response_model=SessionResponse)
def create_session(request: CreateSessionRequest) -> SessionResponse:
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
def list_sessions() -> list[SessionResponse]:
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
def get_session(session_id: str) -> SessionResponse:
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
def end_session(session_id: str) -> dict[str, str]:
    """End a chat session."""
    if chat_engine.end_session(session_id):
        return {"status": "ended", "session_id": session_id}
    raise HTTPException(status_code=404, detail="Session not found")


@router.post("/sessions/{session_id}/message")
def send_and_stream(
    session_id: str, request: AISDKSendRequest
) -> StreamingResponse:
    """Send a message and stream the response — AI SDK Data Stream Protocol v1."""
    session = chat_engine.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if not session.is_active:
        raise HTTPException(status_code=409, detail="Session is inactive")

    # Extract text content from the last user message's parts
    last = request.messages[-1] if request.messages else None
    if not last or last.get("role") != "user":
        raise HTTPException(status_code=400, detail="Last message must be from user")

    content = "".join(
        p.get("text", "") for p in last.get("parts", []) if p.get("type") == "text"
    )
    if not content:
        content = str(last.get("content", ""))
    if not content.strip():
        raise HTTPException(status_code=400, detail="Message content is empty")

    if request.lang and request.lang != "en":
        lang_names = {
            "zh": "Chinese", "ja": "Japanese", "ko": "Korean",
            "es": "Spanish", "fr": "French", "de": "German",
        }
        lang_name = lang_names.get(request.lang, request.lang)
        content = f"[Respond in {lang_name}] {content}"

    try:
        streamer = chat_engine.send_message(session_id, content)
    except ChatNotAvailableError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    def event_generator():
        completed = False
        try:
            yield 'data: {"type":"start"}\n\n'
            for event in streamer.iter_events():
                yield streamer.to_sse(event)
            completed = True
            yield "data: [DONE]\n\n"
        finally:
            # StreamingResponse closes the generator when the client disconnects.
            # The identity guard avoids cancelling a newer run for this session.
            if not completed:
                chat_engine.cancel_stream(session_id, expected_streamer=streamer)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "x-vercel-ai-ui-message-stream": "v1",
        },
    )


@router.post("/sessions/{session_id}/cancel")
def cancel_stream(session_id: str) -> dict[str, str]:
    """Cancel an active streaming response by killing the subprocess."""
    session = chat_engine.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    chat_engine.cancel_stream(session_id)
    return {"status": "cancelled", "session_id": session_id}


@router.get("/sessions/{session_id}/composer", response_model=ComposerStateResponse)
def get_composer_state(session_id: str) -> ComposerStateResponse:
    """Get composer state for UI footer."""
    try:
        state = chat_engine.get_composer_state(session_id)
        return ComposerStateResponse(
            model=state.model,
            is_streaming=state.is_streaming,
            context_tokens=state.context_tokens,
            status=state.status,
            elapsed_ms=state.elapsed_ms,
            first_token_ms=state.first_token_ms,
            total_ms=state.total_ms,
            process_start_ms=state.process_start_ms,
            resumed=state.resumed,
            recent_first_token_avg_ms=state.recent_first_token_avg_ms,
            recent_total_avg_ms=state.recent_total_avg_ms,
            recent_runs=state.recent_runs,
        )
    except Exception as e:
        # Return default if session not found
        return ComposerStateResponse(
            model="unknown",
            is_streaming=False,
            context_tokens=0,
            status="idle",
            elapsed_ms=0,
        )


@router.get("/available")
def check_availability() -> dict[str, Any]:
    """Check if chat functionality is available."""
    cli_available = chat_engine.is_available()

    return {
        "available": cli_available,
        "cli_available": cli_available,
    }


@router.get("/diagnostics")
def check_diagnostics() -> dict[str, Any]:
    """Return slower chat backend diagnostics outside the tab-open path."""
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
        "available": cli_available,
        "cli_available": cli_available,
        "direct_import": direct_import,
        "tmux_available": tmux_available,
        "tmux_pane_found": tmux_pane is not None,
        "tmux_pane_id": tmux_pane,
    }
