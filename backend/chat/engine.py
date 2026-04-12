"""CLI-based chat engine using hermes subprocess."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import threading
import uuid
from datetime import datetime
from typing import Optional

from .models import (
    ChatSession,
    ComposerState,
    StreamingEvent,
)
from .streamer import ChatStreamer

# Regex to match box-drawing decoration lines from hermes CLI output
_BOX_DRAWING_RE = re.compile(r'^[\s\r]*[╭╮╰╯│─┌┐└┘├┤┬┴┼◉◈●▸▹▶▷■□▪▫]+[\s─╭╮╰╯│┌┐└┘├┤┬┴┼]*$')
_SESSION_ID_RE = re.compile(r'^session_id:\s+\S+')
_HEADER_RE = re.compile(r'[╭╰][\s─]*[◉◈●]?\s*(MOTHER|HERMES|hermes)\s*[─╮╯]')


class ChatNotAvailableError(Exception):
    """Raised when chat functionality is not available."""

    pass


class ChatEngine:
    """Chat engine using hermes CLI subprocess with -q (query) and -Q (quiet) flags."""

    _instance: Optional["ChatEngine"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "ChatEngine":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._sessions: dict[str, ChatSession] = {}
        self._streamers: dict[str, ChatStreamer] = {}
        self._processes: dict[str, subprocess.Popen] = {}
        self._initialized = True
        self._hermes_path = shutil.which("hermes")
        self._cli_available = self._check_cli()

    def _check_cli(self) -> bool:
        """Check if hermes CLI is available."""
        if not self._hermes_path:
            return False
        try:
            result = subprocess.run(
                [self._hermes_path, "--version"], capture_output=True, timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False

    def is_available(self) -> bool:
        """Check if chat is available."""
        return self._cli_available

    def create_session(
        self, profile: Optional[str] = None, model: Optional[str] = None
    ) -> ChatSession:
        """Create a new chat session."""
        if not self._cli_available:
            raise ChatNotAvailableError(
                "Hermes CLI not available. Install hermes-agent: pip install hermes-agent"
            )

        session_id = str(uuid.uuid4())[:8]

        session = ChatSession(
            id=session_id,
            profile=profile,
            model=model,
            title=f"Chat {session_id}",
            backend_type="cli",
        )
        self._sessions[session_id] = session

        return session

    def get_session(self, session_id: str) -> Optional[ChatSession]:
        """Get session by ID."""
        return self._sessions.get(session_id)

    def list_sessions(self) -> list[ChatSession]:
        """List all active sessions."""
        return list(self._sessions.values())

    def end_session(self, session_id: str) -> bool:
        """End a chat session."""
        if session_id in self._sessions:
            self._sessions[session_id].is_active = False

            # Kill running process
            if session_id in self._processes:
                try:
                    self._processes[session_id].kill()
                except Exception:
                    pass
                del self._processes[session_id]

            # Cleanup streamer
            if session_id in self._streamers:
                self._streamers[session_id].stop()
                del self._streamers[session_id]

            return True
        return False

    def send_message(
        self,
        session_id: str,
        content: str,
    ) -> ChatStreamer:
        """Send a message using hermes chat -q -Q and stream stdout."""
        session = self._sessions.get(session_id)
        if not session:
            raise ChatNotAvailableError(f"Session {session_id} not found")

        if not session.is_active:
            raise ChatNotAvailableError(f"Session {session_id} is inactive")

        # Clean up previous streamer/process
        if session_id in self._streamers:
            self._streamers[session_id].stop()
        if session_id in self._processes:
            try:
                self._processes[session_id].kill()
            except Exception:
                pass

        streamer = ChatStreamer()
        self._streamers[session_id] = streamer

        # Update session stats
        session.message_count += 1
        session.last_activity = datetime.now()

        # Build command: hermes chat -q "message" -Q (quiet mode)
        cmd = [self._hermes_path, "chat", "-q", content, "-Q"]
        if session.profile:
            cmd.extend(["--profile", session.profile])
        if session.model:
            cmd.extend(["-m", session.model])
        # Tag as tool source so it doesn't clutter user session list
        cmd.extend(["--source", "tool"])

        def _is_decoration_line(line: str) -> bool:
            """Check if a line is CLI decoration (box drawing, headers, session info)."""
            stripped = line.strip().replace('\r', '')
            if not stripped:
                return False
            if _SESSION_ID_RE.match(stripped):
                return True
            if _HEADER_RE.search(stripped):
                return True
            # Lines that are only box-drawing chars, spaces, and label text
            if _BOX_DRAWING_RE.match(stripped):
                return True
            return False

        def run_subprocess():
            try:
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    cwd=os.path.expanduser("~"),
                )
                self._processes[session_id] = process

                # Stream stdout line by line, filtering decoration
                started_content = False
                for line in iter(process.stdout.readline, b""):
                    if streamer._stopped.is_set():
                        break
                    text = line.decode("utf-8", errors="replace")

                    # Skip decoration lines
                    if _is_decoration_line(text):
                        continue

                    # Skip leading empty lines before content starts
                    if not started_content and not text.strip():
                        continue

                    started_content = True

                    # Emit the line for streaming
                    for char in text:
                        streamer.emit_token(char)

                process.wait()

                # Check for errors
                if process.returncode != 0:
                    stderr = process.stderr.read().decode("utf-8", errors="replace")
                    if stderr.strip():
                        streamer.emit_error(f"CLI error: {stderr.strip()}")
                    else:
                        streamer.emit_done()
                else:
                    streamer.emit_done()

            except Exception as e:
                streamer.emit_error(f"Failed to run hermes: {e}")
            finally:
                self._processes.pop(session_id, None)

        threading.Thread(target=run_subprocess, daemon=True).start()

        return streamer

    def get_composer_state(self, session_id: str) -> ComposerState:
        """Get current composer state for UI."""
        session = self._sessions.get(session_id)
        if not session:
            return ComposerState(model="unknown")

        return ComposerState(
            model=session.model or "claude-4-sonnet",
            is_streaming=session_id in self._streamers,
            context_tokens=0,
        )

    def cleanup_all(self) -> None:
        """Clean up all sessions."""
        for session_id in list(self._sessions.keys()):
            self.end_session(session_id)


# Global engine instance
chat_engine = ChatEngine()
