"""TMUX fallback for chat when direct agent import unavailable."""

from __future__ import annotations

import subprocess
import time
from pathlib import Path
from typing import Optional

from .models import ChatSession, StreamingEvent
from .streamer import ChatStreamer


class TmuxChatFallback:
    """Send messages to Hermes via TMUX send-keys."""

    def __init__(self, session_id: str, pane_id: str | None = None):
        self.session_id = session_id
        self.pane_id = pane_id
        self._streamer = ChatStreamer()

    @staticmethod
    def is_available() -> bool:
        """Check if tmux is installed."""
        try:
            result = subprocess.run(["tmux", "-V"], capture_output=True, timeout=2)
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    @staticmethod
    def find_hermes_pane() -> str | None:
        """Find a tmux pane running Hermes CLI."""
        try:
            result = subprocess.run(
                [
                    "tmux",
                    "list-panes",
                    "-a",
                    "-F",
                    "#{pane_id}\t#{pane_current_command}",
                ],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode != 0:
                return None

            for line in result.stdout.strip().split("\n"):
                parts = line.split("\t")
                if len(parts) == 2:
                    pane_id, cmd = parts
                    if "hermes" in cmd.lower():
                        return pane_id
            return None
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return None

    def send_message(self, content: str) -> bool:
        """Send a message to the Hermes pane."""
        if not self.pane_id:
            self.pane_id = self.find_hermes_pane()
            if not self.pane_id:
                return False

        try:
            # Escape special characters for tmux
            escaped = content.replace("'", "'\"'\"'")

            # Send the message followed by Enter
            subprocess.run(
                ["tmux", "send-keys", "-t", self.pane_id, escaped, "Enter"],
                capture_output=True,
                timeout=5,
            )
            return True
        except (
            subprocess.TimeoutExpired,
            FileNotFoundError,
            subprocess.CalledProcessError,
        ):
            return False

    def start_streaming(self) -> StreamingEvent:
        """TMUX fallback can't truly stream - emit warning."""
        self._streamer.emit(
            StreamingEvent(
                type="info",
                data={
                    "message": "TMUX mode: Responses appear when written to database"
                },
            )
        )
        return self._streamer

    def get_streamer(self) -> ChatStreamer:
        """Get the streamer instance."""
        return self._streamer
