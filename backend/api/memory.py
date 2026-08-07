"""Memory endpoints."""

from __future__ import annotations

import sys

if sys.platform == "win32":
    import msvcrt

    def _flock_ex(handle):
        msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
else:
    import fcntl

    def _flock_ex(handle):
        fcntl.flock(handle, fcntl.LOCK_EX)
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.collectors.memory import collect_memory
from backend.collectors.config import collect_config
from backend.collectors.utils import default_hermes_dir
from backend.governance import (
    GovernanceWriteError,
    VerifiedFileActionAdapter,
)
from .serialize import to_dict

router = APIRouter()

ENTRY_DELIMITER = "\n§\n"

MemoryTarget = Literal["memory", "user"]


def _memory_path(target: MemoryTarget) -> Path:
    """Return the path for MEMORY.md or USER.md."""
    memories_dir = Path(default_hermes_dir()) / "memories"
    if target == "user":
        return memories_dir / "USER.md"
    return memories_dir / "MEMORY.md"


def _lock_path(target: MemoryTarget) -> Path:
    return _memory_path(target).with_suffix(".md.lock")


def _read_entries(target: MemoryTarget) -> list[str]:
    """Read and split entries from a memory file."""
    path = _memory_path(target)
    try:
        content = path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return []
    if not content:
        return []
    return [p.strip() for p in content.split("§") if p.strip()]


def _write_entries(target: MemoryTarget, entries: list[str]) -> None:
    """Atomically write entries back to a memory file."""
    path = _memory_path(target)
    content = ENTRY_DELIMITER.join(entries) + "\n" if entries else ""
    adapter = VerifiedFileActionAdapter(
        allowed_roots=[Path(default_hermes_dir())]
    )
    adapter.write_one(path, content.encode("utf-8"), action="memory.write")


def _with_lock(target: MemoryTarget, fn):
    """Execute fn while holding the memory file lock."""
    lock = _lock_path(target)
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.touch(exist_ok=True)
    with open(lock, "r") as lf:
        _flock_ex(lf)
        try:
            return fn()
        except GovernanceWriteError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/memory")
async def get_memory():
    """Memory and user profile state."""
    config = collect_config()
    memory, user = collect_memory(
        memory_char_limit=config.memory_char_limit,
        user_char_limit=config.user_char_limit,
    )
    return {
        "memory": to_dict(memory),
        "user": to_dict(user),
    }


class AddBody(BaseModel):
    target: MemoryTarget
    content: str


class EditBody(BaseModel):
    target: MemoryTarget
    old_text: str
    content: str


class DeleteBody(BaseModel):
    target: MemoryTarget
    old_text: str


@router.post("/memory")
def add_entry(body: AddBody):
    """Add a new memory entry."""
    content = body.content.strip()
    if not content:
        raise HTTPException(400, "content cannot be empty")

    def do():
        entries = _read_entries(body.target)
        for e in entries:
            if e == content:
                raise HTTPException(409, "Duplicate entry")
        entries.append(content)
        _write_entries(body.target, entries)
        return {"ok": True, "entry_count": len(entries)}

    return _with_lock(body.target, do)


@router.put("/memory")
def edit_entry(body: EditBody):
    """Replace a memory entry (matched by old_text substring)."""
    new_content = body.content.strip()
    if not new_content:
        raise HTTPException(400, "content cannot be empty")

    def do():
        entries = _read_entries(body.target)
        matches = [i for i, e in enumerate(entries) if body.old_text in e]
        if not matches:
            raise HTTPException(404, "No entry matches old_text")
        if len(matches) > 1:
            raise HTTPException(409, "Multiple entries match — use a more specific old_text")
        entries[matches[0]] = new_content
        _write_entries(body.target, entries)
        return {"ok": True, "entry_count": len(entries)}

    return _with_lock(body.target, do)


@router.delete("/memory")
def delete_entry(body: DeleteBody):
    """Remove a memory entry (matched by old_text substring)."""

    def do():
        entries = _read_entries(body.target)
        matches = [i for i, e in enumerate(entries) if body.old_text in e]
        if not matches:
            raise HTTPException(404, "No entry matches old_text")
        if len(matches) > 1:
            raise HTTPException(409, "Multiple entries match — use a more specific old_text")
        entries.pop(matches[0])
        _write_entries(body.target, entries)
        return {"ok": True, "entry_count": len(entries)}

    return _with_lock(body.target, do)
