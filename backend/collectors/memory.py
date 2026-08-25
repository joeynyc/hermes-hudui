"""Parse Hermes memory files (MEMORY.md and USER.md)."""

from __future__ import annotations

import re
from pathlib import Path

from .models import MemoryEntry, MemoryState
from .utils import default_hermes_dir

# Capacity limits (from Hermes system prompt injection)
MEMORY_MAX_CHARS = 2200
USER_MAX_CHARS = 1375

# Category detection patterns
CORRECTION_PATTERNS = [
    r"gotcha", r"don't", r"caught", r"wrong", r"verify before",
    r"supersedes", r"not usable", r"doesn't work", r"won't help",
    r"not yet confirmed", r"was stuck", r"may need manual",
]

ENVIRONMENT_PATTERNS = [
    r"WSL", r"Ubuntu", r"installed", r"configured", r"version",
    r"SSD", r"GPU", r"RTX", r"backend", r"systemd", r"API_KEY",
    r"provider", r"build:", r"tok/s",
]

TODO_PATTERNS = [
    r"TODO:", r"needs to", r"not yet",
]

PROJECT_PATTERNS = [
    r"project", r"~/projects/", r"repo", r"agent",

]

PREFERENCE_PATTERNS = [
    r"preferred", r"expects", r"familiar with", r"interested in",
    r"push back", r"voice-to-text", r"phonetic", r"platform:",
    r"switched to", r"long-time", r"default model",
]


def _categorize(text: str, source: str) -> str:
    """Categorize a memory entry by content analysis."""
    lower = text.lower()

    # Corrections are highest priority — check first
    for p in CORRECTION_PATTERNS:
        if re.search(p, text, re.IGNORECASE):
            return "correction"

    if source == "user":
        for p in PREFERENCE_PATTERNS:
            if re.search(p, text, re.IGNORECASE):
                return "preference"

    for p in TODO_PATTERNS:
        if re.search(p, text, re.IGNORECASE):
            return "todo"

    for p in PROJECT_PATTERNS:
        if re.search(p, text, re.IGNORECASE):
            return "project"

    for p in ENVIRONMENT_PATTERNS:
        if re.search(p, text, re.IGNORECASE):
            return "environment"

    return "other"


def _parse_entries(content: str, source: str) -> list[MemoryEntry]:
    """Split § delimited content into categorized entries."""
    raw = content.strip()
    if not raw:
        return []

    parts = [p.strip() for p in raw.split("§") if p.strip()]
    return [MemoryEntry(text=p, category=_categorize(p, source)) for p in parts]


def collect_memory(
    hermes_dir: str | None = None,
    memory_char_limit: int = MEMORY_MAX_CHARS,
    user_char_limit: int = USER_MAX_CHARS,
) -> tuple[MemoryState, MemoryState]:
    """Collect memory and user profile state.

    Returns:
        (memory_state, user_state)
    """
    if hermes_dir is None:
        hermes_dir = default_hermes_dir(hermes_dir)

    memories_dir = Path(hermes_dir) / "memories"

    # Parse MEMORY.md
    memory_path = memories_dir / "MEMORY.md"
    memory_content = ""
    if memory_path.exists():
        memory_content = memory_path.read_text(encoding="utf-8")

    memory_entries = _parse_entries(memory_content, "memory")
    memory_state = MemoryState(
        entries=memory_entries,
        total_chars=len(memory_content),
        max_chars=memory_char_limit,
        source="memory",
    )

    # Parse USER.md
    user_path = memories_dir / "USER.md"
    user_content = ""
    if user_path.exists():
        user_content = user_path.read_text(encoding="utf-8")

    user_entries = _parse_entries(user_content, "user")
    user_state = MemoryState(
        entries=user_entries,
        total_chars=len(user_content),
        max_chars=user_char_limit,
        source="user",
    )

    return memory_state, user_state
