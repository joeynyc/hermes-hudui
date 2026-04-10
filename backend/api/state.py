"""Full HUD state endpoint."""

from fastapi import APIRouter
from starlette.concurrency import run_in_threadpool
from backend.collectors.collect import collect_all
from .serialize import to_dict

router = APIRouter()


@router.get("/state")
async def get_state():
    """Collect core state: config, memory, user, skills, sessions, timeline."""
    return await run_in_threadpool(lambda: to_dict(collect_all()))
