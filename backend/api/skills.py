"""Skills endpoints."""

from fastapi import APIRouter

from backend.collectors.skills import collect_skills
from .serialize import to_dict
from .profile_scope import resolve_profile_scope

router = APIRouter()


@router.get("/skills")
async def get_skills(profile: str | None = None):
    profile_name, hermes_dir = resolve_profile_scope(profile)
    state = collect_skills(hermes_dir)
    result = to_dict(state)
    result["profile"] = profile_name
    # These are methods, not properties, so they're not auto-serialized
    result["by_category"] = to_dict(state.by_category())
    result["category_counts"] = to_dict(state.category_counts())
    result["recently_modified"] = to_dict(state.recently_modified(10))
    return result
