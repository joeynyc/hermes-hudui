"""SSE streaming handler for chat responses."""

from __future__ import annotations

import json
import queue
import threading
from typing import Any, Iterator

from .models import StreamingEvent, ToolCall, ToolStatus


class ChatStreamer:
    """Manages SSE streaming for a single chat session."""

    def __init__(self):
        self._queue: queue.Queue[StreamingEvent | None] = queue.Queue()
        self._stopped = threading.Event()
        self._current_message: str = ""
        self._current_tools: dict[str, ToolCall] = {}

    def emit(self, event: StreamingEvent) -> None:
        """Queue an event for streaming."""
        if not self._stopped.is_set():
            self._queue.put(event)

    def emit_token(self, token: str) -> None:
        """Emit a text token."""
        self._current_message += token
        self.emit(StreamingEvent(type="token", data={"text": token}))

    def emit_tool_start(self, tool_id: str, name: str, arguments: dict) -> None:
        """Emit tool call start."""
        tool = ToolCall(id=tool_id, name=name, arguments=arguments)
        self._current_tools[tool_id] = tool
        self.emit(
            StreamingEvent(
                type="tool_start",
                data={"id": tool_id, "name": name, "arguments": arguments},
            )
        )

    def emit_tool_end(
        self, tool_id: str, result: Any = None, error: str | None = None
    ) -> None:
        """Emit tool call completion."""
        if tool_id in self._current_tools:
            tool = self._current_tools[tool_id]
            tool.status = ToolStatus.ERROR if error else ToolStatus.COMPLETE
            tool.result = result
            tool.error = error

        self.emit(
            StreamingEvent(
                type="tool_end", data={"id": tool_id, "result": result, "error": error}
            )
        )

    def emit_reasoning(self, content: str) -> None:
        """Emit reasoning/thinking content."""
        self.emit(StreamingEvent(type="reasoning", data={"content": content}))

    def emit_done(self) -> None:
        """Signal completion."""
        self.emit(StreamingEvent(type="done", data={}))
        self._queue.put(None)  # Sentinel to stop iteration

    def emit_error(self, error: str) -> None:
        """Emit error event."""
        self.emit(StreamingEvent(type="error", data={"message": error}))
        self._queue.put(None)

    def stop(self) -> None:
        """Stop the stream."""
        self._stopped.set()
        self._queue.put(None)

    def iter_events(self) -> Iterator[StreamingEvent]:
        """Iterate over events for SSE."""
        while not self._stopped.is_set():
            event = self._queue.get()
            if event is None:
                break
            yield event

    def to_sse(self, event: StreamingEvent) -> str:
        """Convert event to SSE format."""
        return f"data: {json.dumps({'type': event.type, 'data': event.data})}\n\n"
