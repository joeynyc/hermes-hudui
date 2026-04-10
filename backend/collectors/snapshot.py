"""Snapshot Hermes HUD state for diff tracking over time.

Run this daily (via cron or hermes cron) to build a history of growth.
Snapshots are stored as JSONL in ~/.hermes-hud/snapshots.jsonl
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

from .collect import collect_all
from .utils import default_hermes_dir
from .models import HUDSnapshot

def _snapshot_dir(hermes_dir: str | None = None) -> str:
    """Return the snapshot directory, respecting the hermes_dir if provided."""
    base = hermes_dir if hermes_dir else default_hermes_dir()
    return os.path.join(base, ".hud")


def _snapshot_file(hermes_dir: str | None = None) -> str:
    """Return the current snapshot file path."""
    return os.path.join(_snapshot_dir(hermes_dir), "snapshots.jsonl")


def take_snapshot(hermes_dir: str | None = None) -> HUDSnapshot:
    """Collect current state and create a snapshot."""
    state = collect_all(hermes_dir)

    return HUDSnapshot(
        timestamp=state.collected_at,
        memory_entry_count=state.memory.entry_count,
        memory_chars=state.memory.total_chars,
        user_entry_count=state.user.entry_count,
        user_chars=state.user.total_chars,
        skill_count=state.skills.total,
        custom_skill_count=state.skills.custom_count,
        session_count=state.sessions.total_sessions,
        total_messages=state.sessions.total_messages,
        total_tool_calls=state.sessions.total_tool_calls,
        total_tokens=state.sessions.total_tokens,
        categories=sorted(state.skills.category_counts().keys()),
    )


def save_snapshot(snap: HUDSnapshot, hermes_dir: str | None = None) -> str:
    """Append snapshot to JSONL file."""
    os.makedirs(_snapshot_dir(hermes_dir), exist_ok=True)
    snapshot_file = _snapshot_file(hermes_dir)

    record = {
        "timestamp": snap.timestamp.isoformat(),
        "memory_entries": snap.memory_entry_count,
        "memory_chars": snap.memory_chars,
        "user_entries": snap.user_entry_count,
        "user_chars": snap.user_chars,
        "skills": snap.skill_count,
        "custom_skills": snap.custom_skill_count,
        "sessions": snap.session_count,
        "messages": snap.total_messages,
        "tool_calls": snap.total_tool_calls,
        "tokens": snap.total_tokens,
        "categories": snap.categories,
    }

    with open(snapshot_file, "a") as f:
        f.write(json.dumps(record) + "\n")

    return snapshot_file


def load_snapshots(hermes_dir: str | None = None) -> list[dict]:
    """Load all historical snapshots."""
    snapshot_file = _snapshot_file(hermes_dir)
    if not os.path.exists(snapshot_file):
        return []

    snapshots = []
    with open(snapshot_file) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    snapshots.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return snapshots


def diff_report(current: dict, previous: dict) -> str:
    """Generate a human-readable diff between two snapshots."""
    lines = []
    fields = [
        ("sessions", "Sessions"),
        ("messages", "Messages"),
        ("tool_calls", "Tool calls"),
        ("skills", "Skills"),
        ("custom_skills", "Custom skills"),
        ("memory_entries", "Memory entries"),
        ("user_entries", "User entries"),
        ("tokens", "Tokens"),
    ]

    for key, label in fields:
        cur = current.get(key, 0)
        prev = previous.get(key, 0)
        delta = cur - prev
        if delta > 0:
            lines.append(f"  ↑ {label}: {prev} → {cur} (+{delta})")
        elif delta < 0:
            lines.append(f"  ↓ {label}: {prev} → {cur} ({delta})")

    # New categories
    cur_cats = set(current.get("categories", []))
    prev_cats = set(previous.get("categories", []))
    new_cats = cur_cats - prev_cats
    if new_cats:
        lines.append(f"  ★ New categories: {', '.join(sorted(new_cats))}")

    return "\n".join(lines) if lines else "  No changes."


def main():
    """Take a snapshot and optionally show diff."""
    snap = take_snapshot()
    path = save_snapshot(snap)

    print(f"Snapshot saved to {path}")
    print(f"  Timestamp: {snap.timestamp:%Y-%m-%d %H:%M:%S}")
    print(f"  Sessions: {snap.session_count}")
    print(f"  Messages: {snap.total_messages}")
    print(f"  Skills: {snap.skill_count} ({snap.custom_skill_count} custom)")
    print(f"  Memory: {snap.memory_entry_count} entries ({snap.memory_chars} chars)")
    print(f"  User: {snap.user_entry_count} entries ({snap.user_chars} chars)")
    print()

    # Show diff from previous snapshot if available
    snapshots = load_snapshots()
    if len(snapshots) >= 2:
        previous = snapshots[-2]
        current = snapshots[-1]
        prev_time = previous.get("timestamp", "unknown")
        print(f"Changes since {prev_time}:")
        print(diff_report(current, previous))
    else:
        print("First snapshot — no diff available yet.")


if __name__ == "__main__":
    main()
