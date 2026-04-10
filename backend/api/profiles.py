"""Profiles endpoint."""

from fastapi import APIRouter
from starlette.concurrency import run_in_threadpool
from backend.collectors.profiles import collect_profiles
from .serialize import to_dict

router = APIRouter()


@router.get("/profiles")
async def get_profiles():
    return await run_in_threadpool(lambda: to_dict(collect_profiles()))
