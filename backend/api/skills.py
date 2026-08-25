"""Skills endpoints."""

from fastapi import APIRouter

from backend.collectors.skills import collect_skills
from .serialize import to_dict

router = APIRouter()


@router.get("/skills")
def get_skills():
    state = collect_skills()
    result = to_dict(state)
    # These are methods, not properties, so they're not auto-serialized
    result["by_category"] = to_dict(state.by_category())
    result["category_counts"] = to_dict(state.category_counts())
    result["recently_modified"] = to_dict(state.recently_modified(10))
    return result
