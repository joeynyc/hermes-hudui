"""Projects endpoint."""

from fastapi import APIRouter

from backend.collectors.projects import collect_projects
from .serialize import to_dict

router = APIRouter()


@router.get("/projects")
def get_projects():
    return to_dict(collect_projects())
