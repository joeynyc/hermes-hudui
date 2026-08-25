"""Timeline endpoint."""

from fastapi import APIRouter

from backend.collectors.collect import collect_all
from .serialize import to_dict

router = APIRouter()


@router.get("/timeline")
def get_timeline():
    state = collect_all()
    return to_dict(state.timeline)
