from fastapi import APIRouter
from starlette.concurrency import run_in_threadpool
from backend.collectors.cron import collect_cron
from .profile_scope import collect_with_profile

router = APIRouter()


@router.get("/cron")
async def get_cron(profile: str | None = None):
    return await run_in_threadpool(collect_with_profile, collect_cron, profile)
