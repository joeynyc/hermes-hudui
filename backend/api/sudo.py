"""Sudo endpoint."""

from fastapi import APIRouter

from backend.collectors.sudo import collect_sudo
from .serialize import to_dict

router = APIRouter()


@router.get("/sudo")
def get_sudo():
    return to_dict(collect_sudo())
