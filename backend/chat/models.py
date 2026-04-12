"""Chat data models for Agent Chat feature."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class MessageRole(Enum):
    """Message role types."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class ToolStatus(Enum):
    """Tool call execution status."""

    RUNNING = "running"
    COMPLETE = "complete"
    ERROR = "error"


@dataclass
class ToolCall:
    """Represents a tool invocation."""

    id: str
    name: str
    arguments: dict[str, Any]
    status: ToolStatus = ToolStatus.RUNNING
    result: Optional[Any] = None
    error: Optional[str] = None
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None


@dataclass
class ChatMessage:
    """A chat message in a conversation."""

    id: str
    role: MessageRole
    content: str
    session_id: str
    timestamp: datetime = field(default_factory=datetime.now)
    tool_calls: list[ToolCall] = field(default_factory=list)
    reasoning: Optional[str] = None
    token_count: Optional[int] = None
    model: Optional[str] = None
    parent_id: Optional[str] = None  # For message threading/editing


@dataclass
class StreamingEvent:
    """Event for SSE streaming."""

    type: str  # 'token', 'tool_start', 'tool_end', 'reasoning', 'done', 'error'
    data: dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class ChatSession:
    """An active chat session."""

    id: str
    profile: Optional[str] = None
    model: Optional[str] = None
    title: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)
    message_count: int = 0
    total_tokens: int = 0
    is_active: bool = True
    backend_type: str = "unknown"  # 'direct', 'tmux', 'unavailable'


@dataclass
class ComposerState:
    """State for the chat composer UI."""

    model: str
    is_streaming: bool = False
    current_tool: Optional[ToolCall] = None
    context_tokens: int = 0
    estimated_cost: float = 0.0
