"""Full HUD state endpoint."""

from fastapi import APIRouter

from backend.collectors.collect import collect_all
from .serialize import to_dict

router = APIRouter()


@router.get("/state")
def get_state():
    """Collect core state: config, memory, user, skills, sessions, timeline."""
    state = collect_all()
    return to_dict(state)
