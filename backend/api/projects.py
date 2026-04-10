"""Projects endpoint."""

from fastapi import APIRouter
from starlette.concurrency import run_in_threadpool
from backend.collectors.projects import collect_projects
from .serialize import to_dict

router = APIRouter()


@router.get("/projects")
async def get_projects():
    return await run_in_threadpool(lambda: to_dict(collect_projects()))
