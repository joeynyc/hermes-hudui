"""CLI-based chat engine using hermes subprocess."""

from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
import subprocess
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from backend.collectors.utils import default_hermes_dir, load_yaml
from .models import (
    ChatSession,
    ComposerState,
)
from .streamer import ChatStreamer

# Regex to match box-drawing decoration lines from hermes CLI output
_BOX_DRAWING_RE = re.compile(
    r"^[\s\r]*[╭╮╰╯│─┌┐└┘├┤┬┴┼◉◈●▸▹▶▷■□▪▫]+[\s─╭╮╰╯│┌┐└┘├┤┬┴┼]*$"
)
# Lines starting with a box border character — top/bottom borders or panel content
_BOX_BORDER_START_RE = re.compile(r"^[\s\r]*[╭╰┌└]─")
_BOX_CONTENT_RE = re.compile(r"^[\s\r]*│(.*)│[\s\r]*$")
_SESSION_ID_RE = re.compile(r"^session_id:\s+(\S+)")
_HEADER_RE = re.compile(r"[╭╰][\s─]*[◉◈●]?\s*(MOTHER|HERMES|hermes)\s*[─╮╯]")
# Hermes system warning lines (context compression, etc.) — not part of the model response
_WARNING_RE = re.compile(r"^⚠")


def _emit_tool_events(streamer: "ChatStreamer", hermes_session_id: str) -> None:
    """Query state.db for tool calls and reasoning from the hermes session and emit SSE events."""
    db_path = Path(default_hermes_dir()) / "state.db"
    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                """SELECT tool_calls, reasoning FROM messages
                   WHERE session_id = ?
                     AND (tool_calls IS NOT NULL OR (reasoning IS NOT NULL AND reasoning != ''))
                   ORDER BY timestamp ASC""",
                (hermes_session_id,),
            ).fetchall()
        finally:
            conn.close()
    except Exception:
        return

    # Emit every distinct reasoning block in timestamp order (interleaved with
    # tool calls), not just the first — multi-step agents write reasoning per
    # message. The set guards against a row's reasoning appearing more than once.
    emitted_reasoning: set[str] = set()
    for row in rows:
        reasoning = row["reasoning"]
        if reasoning and reasoning not in emitted_reasoning:
            streamer.emit_reasoning(reasoning)
            emitted_reasoning.add(reasoning)

        if row["tool_calls"]:
            try:
                calls = json.loads(row["tool_calls"])
                if not isinstance(calls, list):
                    calls = [calls]
                for call in calls:
                    fn = call.get("function", {})
                    tool_id = (
                        call.get("id") or call.get("call_id") or fn.get("name", "tool")
                    )
                    name = fn.get("name", "unknown")
                    try:
                        args = json.loads(fn.get("arguments", "{}"))
                    except Exception:
                        args = {}
                    streamer.emit_tool_start(tool_id, name, args)
                    streamer.emit_tool_end(tool_id)
            except Exception:
                pass


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
        self._run_state: dict[str, dict[str, float | str | bool | None]] = {}
        self._run_history: dict[str, list[dict[str, int | bool | str | None]]] = {}
        self._state_lock = threading.RLock()
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

    def _configured_model(self, profile: Optional[str] = None) -> str:
        """Return the configured Hermes model for the default or named profile."""
        hermes_path = Path(default_hermes_dir())
        if profile and profile != "default":
            hermes_path = hermes_path / "profiles" / profile

        config_path = hermes_path / "config.yaml"
        if not config_path.exists():
            return "unknown"

        try:
            config = load_yaml(config_path.read_text(encoding="utf-8"))
        except Exception:
            return "unknown"

        model_cfg = config.get("model") if isinstance(config, dict) else None
        if isinstance(model_cfg, str):
            return model_cfg.strip() or "unknown"
        if isinstance(model_cfg, dict):
            model = str(
                model_cfg.get("default") or model_cfg.get("model") or ""
            ).strip()
            return model or "unknown"
        return "unknown"

    def create_session(
        self, profile: Optional[str] = None, model: Optional[str] = None
    ) -> ChatSession:
        """Create a new chat session."""
        if not self._cli_available:
            raise ChatNotAvailableError(
                "Hermes CLI not available. Run: pip install 'hermes-hudui[chat]'  "
                "(quotes required in zsh)"
            )

        session_id = str(uuid.uuid4())[:8]

        session = ChatSession(
            id=session_id,
            profile=profile,
            model=model,
            title=f"Chat {session_id}",
            backend_type="cli",
        )
        with self._state_lock:
            self._sessions[session_id] = session

        return session

    def get_session(self, session_id: str) -> Optional[ChatSession]:
        """Get session by ID."""
        with self._state_lock:
            return self._sessions.get(session_id)

    def list_sessions(self) -> list[ChatSession]:
        """List all active sessions."""
        with self._state_lock:
            return list(self._sessions.values())

    @staticmethod
    def _terminate_process(process: subprocess.Popen) -> None:
        """Terminate a child process, escalating if it does not exit."""
        try:
            process.terminate()
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            try:
                process.kill()
                process.wait(timeout=1)
            except Exception:
                pass
        except Exception:
            try:
                process.kill()
            except Exception:
                pass

    def _update_run_state(
        self, session_id: str, run_id: str, **updates: float | str | bool | None
    ) -> bool:
        """Update state only when the worker still owns the current run."""
        with self._state_lock:
            state = self._run_state.get(session_id)
            if not state or state.get("run_id") != run_id:
                return False
            state.update(updates)
            return True

    def end_session(self, session_id: str) -> bool:
        """End a chat session."""
        with self._state_lock:
            session = self._sessions.get(session_id)
            if session is None:
                return False
            session.is_active = False
            process = self._processes.pop(session_id, None)
            streamer = self._streamers.pop(session_id, None)

        if streamer:
            streamer.stop()
        if process:
            self._terminate_process(process)
        return True

    def send_message(
        self,
        session_id: str,
        content: str,
    ) -> ChatStreamer:
        """Send a message using hermes chat -q -Q and stream stdout."""
        streamer = ChatStreamer()
        run_id = str(uuid.uuid4())
        with self._state_lock:
            session = self._sessions.get(session_id)
            if not session:
                raise ChatNotAvailableError(f"Session {session_id} not found")
            if not session.is_active:
                raise ChatNotAvailableError(f"Session {session_id} is inactive")

            previous_streamer = self._streamers.get(session_id)
            previous_process = self._processes.get(session_id)
            self._streamers[session_id] = streamer

            # Update session stats
            session.message_count += 1
            session.last_activity = datetime.now()
            self._run_state[session_id] = {
                "run_id": run_id,
                "status": "starting_hermes",
                "started_at": time.monotonic(),
                "process_started_at": None,
                "first_token_at": None,
                "finished_at": None,
                "resumed": bool(session.hermes_session_id),
            }

        if previous_streamer:
            previous_streamer.stop()
        if previous_process:
            self._terminate_process(previous_process)

        # Build command: hermes chat -q "message" -Q (quiet mode)
        cmd = [self._hermes_path, "chat", "-q", content, "-Q"]
        if session.profile:
            cmd.extend(["--profile", session.profile])
        if session.model:
            cmd.extend(["-m", session.model])
        if session.hermes_session_id:
            cmd.extend(["--resume", session.hermes_session_id])
        # Tag as tool source so it doesn't clutter user session list
        cmd.extend(["--source", "tool"])

        def _is_decoration_line(line: str) -> bool:
            """Check if a line is CLI decoration (box drawing, headers)."""
            stripped = line.strip().replace("\r", "")
            if not stripped:
                return False
            if _HEADER_RE.search(stripped):
                return True
            if _BOX_DRAWING_RE.match(stripped):
                return True
            # Top/bottom border lines (╭─ ... or ╰─ ...) — skip entirely
            if _BOX_BORDER_START_RE.match(line):
                return True
            return False

        def _extract_box_content(line: str) -> str | None:
            """If line is │ content │, return the inner content. Otherwise None."""
            m = _BOX_CONTENT_RE.match(line)
            return m.group(1).strip() if m else None

        def run_subprocess():
            process: subprocess.Popen | None = None
            try:
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    cwd=os.path.expanduser("~"),
                )
                with self._state_lock:
                    owns_run = (
                        self._streamers.get(session_id) is streamer
                        and self._run_state.get(session_id, {}).get("run_id") == run_id
                        and not streamer._stopped.is_set()
                    )
                    if owns_run:
                        self._processes[session_id] = process
                if not owns_run:
                    self._terminate_process(process)
                    return
                self._update_run_state(
                    session_id,
                    run_id,
                    process_started_at=time.monotonic(),
                    status="connecting_model",
                )

                # Stream stdout in chunks; process complete lines through the
                # decoration filter and emit partial trailing content immediately
                # once real content has started (avoids waiting for \n).
                started_content = False
                in_warning_block = False
                line_buf = b""

                # hermes v0.10+ prints "session_id: <ID>" to stderr so stdout
                # stays clean for piping. Drain stderr concurrently — pull the
                # session_id line out and keep the rest for error reporting.
                captured_session_id: list[str] = []
                stderr_lines: list[str] = []

                def _drain_stderr():
                    for raw in process.stderr:
                        text = raw.decode("utf-8", errors="replace").rstrip("\n")
                        m = _SESSION_ID_RE.match(text.strip())
                        if m:
                            captured_session_id.append(m.group(1))
                        elif text.strip():
                            stderr_lines.append(text)

                stderr_thread = threading.Thread(target=_drain_stderr, daemon=True)
                stderr_thread.start()

                def _process_line(raw_line: bytes) -> None:
                    nonlocal started_content, in_warning_block
                    text = raw_line.decode("utf-8", errors="replace")
                    stripped = text.strip()

                    if _WARNING_RE.match(stripped):
                        in_warning_block = True
                        return
                    if in_warning_block:
                        if not stripped:
                            in_warning_block = False
                            return
                        if text[0] in (" ", "\t"):
                            return
                        in_warning_block = False

                    if _is_decoration_line(text):
                        return

                    box_inner = _extract_box_content(text)
                    if box_inner is not None:
                        if box_inner:
                            text = box_inner + "\n"
                            stripped = text.strip()
                        else:
                            return

                    if not started_content and not stripped:
                        return

                    started_content = True
                    with self._state_lock:
                        state = self._run_state.get(session_id)
                        if state and state.get("run_id") == run_id:
                            if state.get("first_token_at") is None:
                                state["first_token_at"] = time.monotonic()
                            state["status"] = "streaming"
                    streamer.emit_token(text)

                while True:
                    if streamer._stopped.is_set():
                        break
                    try:
                        chunk = process.stdout.read1(4096)
                    except Exception:
                        break
                    if not chunk:
                        break

                    line_buf += chunk
                    # Process all complete lines
                    while b"\n" in line_buf:
                        line, line_buf = line_buf.split(b"\n", 1)
                        _process_line(line + b"\n")
                    if started_content and line_buf:
                        _process_line(line_buf)
                        line_buf = b""

                # Flush any remaining partial line
                if line_buf:
                    _process_line(line_buf)

                process.wait()
                stderr_thread.join(timeout=2)

                hermes_session_id = (
                    captured_session_id[0] if captured_session_id else None
                )
                if hermes_session_id:
                    with self._state_lock:
                        if self._run_state.get(session_id, {}).get("run_id") == run_id:
                            session.hermes_session_id = hermes_session_id

                # Emit tool calls and reasoning from state.db
                if hermes_session_id and not streamer._stopped.is_set():
                    self._update_run_state(
                        session_id, run_id, status="finalizing_tools"
                    )
                    _emit_tool_events(streamer, hermes_session_id)

                if process.returncode != 0:
                    self._update_run_state(session_id, run_id, status="error")
                    error_detail = (
                        "\n".join(stderr_lines)
                        or f"hermes exited with code {process.returncode}"
                    )
                    streamer.emit_error("CLI error: " + error_detail)
                else:
                    self._update_run_state(session_id, run_id, status="complete")
                    streamer.emit_done()

            except Exception as e:
                self._update_run_state(session_id, run_id, status="error")
                streamer.emit_error(f"Failed to run hermes: {e}")
            finally:
                with self._state_lock:
                    state = self._run_state.get(session_id)
                    if state and state.get("run_id") == run_id:
                        state["finished_at"] = time.monotonic()
                        self._record_run_history_locked(session_id)
                    if (
                        process is not None
                        and self._processes.get(session_id) is process
                    ):
                        self._processes.pop(session_id, None)
                    if self._streamers.get(session_id) is streamer:
                        self._streamers.pop(session_id, None)

        threading.Thread(target=run_subprocess, daemon=True).start()

        return streamer

    def cancel_stream(
        self, session_id: str, expected_streamer: ChatStreamer | None = None
    ) -> bool:
        """Stop the active run, optionally only if the caller still owns it."""
        with self._state_lock:
            current_streamer = self._streamers.get(session_id)
            if (
                expected_streamer is not None
                and current_streamer is not expected_streamer
            ):
                return False
            process = self._processes.pop(session_id, None)
            streamer = self._streamers.pop(session_id, None)
            if process is None and streamer is None:
                return False
            state = self._run_state.setdefault(
                session_id, {"started_at": time.monotonic()}
            )
            state["status"] = "cancelling"

        if streamer:
            streamer.stop()
        if process:
            self._terminate_process(process)

        with self._state_lock:
            state = self._run_state.get(session_id)
            if state is not None:
                state["status"] = "cancelled"
                state["finished_at"] = time.monotonic()
                self._record_run_history_locked(session_id)
        return True

    def _record_run_history(self, session_id: str) -> None:
        """Store a compact timing summary for recent chat turns."""
        with self._state_lock:
            self._record_run_history_locked(session_id)

    def _record_run_history_locked(self, session_id: str) -> None:
        """Store run history while ``_state_lock`` is held."""
        state = self._run_state.get(session_id) or {}
        if state.get("history_recorded"):
            return
        started_at = state.get("started_at")
        finished_at = state.get("finished_at")
        if not isinstance(started_at, float) or not isinstance(finished_at, float):
            return

        process_started_at = state.get("process_started_at")
        first_token_at = state.get("first_token_at")
        sample = {
            "status": str(state.get("status") or "unknown"),
            "process_start_ms": (
                int((process_started_at - started_at) * 1000)
                if isinstance(process_started_at, float)
                else None
            ),
            "first_token_ms": (
                int((first_token_at - started_at) * 1000)
                if isinstance(first_token_at, float)
                else None
            ),
            "total_ms": int((finished_at - started_at) * 1000),
            "resumed": bool(state.get("resumed")),
        }
        history = self._run_history.setdefault(session_id, [])
        history.append(sample)
        del history[:-20]
        state["history_recorded"] = True

    def get_composer_state(self, session_id: str) -> ComposerState:
        """Get current composer state for UI."""
        with self._state_lock:
            session = self._sessions.get(session_id)
            if not session:
                return ComposerState(model="unknown")
            process = self._processes.get(session_id)
            run_state = dict(self._run_state.get(session_id) or {})
            history = list(self._run_history.get(session_id, []))

        is_streaming = False
        if process is not None:
            try:
                is_streaming = process.poll() is None
            except Exception:
                is_streaming = True

        started_at = run_state.get("started_at")
        first_token_at = run_state.get("first_token_at")
        process_started_at = run_state.get("process_started_at")
        finished_at = run_state.get("finished_at")
        now = time.monotonic()
        end_at = finished_at if isinstance(finished_at, float) else now

        elapsed_ms = (
            int((end_at - started_at) * 1000) if isinstance(started_at, float) else 0
        )
        first_token_ms = (
            int((first_token_at - started_at) * 1000)
            if isinstance(started_at, float) and isinstance(first_token_at, float)
            else None
        )
        process_start_ms = (
            int((process_started_at - started_at) * 1000)
            if isinstance(started_at, float) and isinstance(process_started_at, float)
            else None
        )
        total_ms = (
            int((finished_at - started_at) * 1000)
            if isinstance(started_at, float) and isinstance(finished_at, float)
            else None
        )

        status = str(
            run_state.get("status") or ("streaming" if is_streaming else "idle")
        )
        first_token_samples = [
            item["first_token_ms"]
            for item in history
            if isinstance(item.get("first_token_ms"), int)
        ]
        total_samples = [
            item["total_ms"]
            for item in history
            if isinstance(item.get("total_ms"), int)
        ]

        return ComposerState(
            model=session.model or self._configured_model(session.profile),
            is_streaming=is_streaming,
            status=status,
            elapsed_ms=elapsed_ms,
            first_token_ms=first_token_ms,
            total_ms=total_ms,
            process_start_ms=process_start_ms,
            resumed=bool(run_state.get("resumed")),
            recent_first_token_avg_ms=(
                int(sum(first_token_samples) / len(first_token_samples))
                if first_token_samples
                else None
            ),
            recent_total_avg_ms=(
                int(sum(total_samples) / len(total_samples)) if total_samples else None
            ),
            recent_runs=len(history),
            context_tokens=0,
        )

    def cleanup_all(self) -> None:
        """Clean up all sessions."""
        with self._state_lock:
            session_ids = list(self._sessions)
        for session_id in session_ids:
            self.end_session(session_id)


# Global engine instance
chat_engine = ChatEngine()
