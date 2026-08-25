"""Providers (OAuth status) endpoint."""

from fastapi import APIRouter

from backend.collectors.providers import collect_providers
from .serialize import to_dict

router = APIRouter()


@router.get("/providers")
def get_providers():
    return to_dict(collect_providers())
