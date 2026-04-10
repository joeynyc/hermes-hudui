"""Skills endpoints."""

from pathlib import Path
from fastapi import APIRouter, HTTPException, Query

from backend.collectors.skills import collect_skills
from backend.collectors.utils import default_hermes_dir
from .serialize import to_dict

from .profile_scope import resolve_profile_scope

router = APIRouter()


@router.get("/skills")
async def get_skills(profile: str | None = None):
    """List all skills, optionally scoped by profile."""
    profile_name, hermes_dir = resolve_profile_scope(profile)
    state = collect_skills(hermes_dir)
    result = to_dict(state)
    # These are methods, not properties, so they're not auto-serialized
    result["profile"] = profile_name
    result["by_category"] = to_dict(state.by_category())
    result["category_counts"] = to_dict(state.category_counts())
    result["recently_modified"] = to_dict(state.recently_modified(10))
    return result


@router.get("/skills/content")
async def get_skill_content(path: str = Query(..., description="Absolute path to SKILL.md")):
    """Return the raw content of a SKILL.md file."""
    try:
        requested_path = Path(path).resolve()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid path format")

    # Safety check: must be within hermes_dir
    allowed_root = Path(default_hermes_dir()).resolve()
    if not str(requested_path).startswith(str(allowed_root)):
        raise HTTPException(status_code=403, detail="Path outside allowed directory")

    if not requested_path.exists() or not requested_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    if requested_path.name != "SKILL.md":
        raise HTTPException(status_code=400, detail="Only SKILL.md files are accessible")

    try:
        return {"content": requested_path.read_text(encoding="utf-8")}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading file: {str(e)}")
