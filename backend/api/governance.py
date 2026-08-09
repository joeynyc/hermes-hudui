"""Read-only ATLAS Beacon governance status endpoint."""

from fastapi import APIRouter

from backend.governance.progress import PlanProgressStore

router = APIRouter()


@router.get("/governance/plan")
def get_governance_plan():
    observation = PlanProgressStore().read()
    progress = observation.progress
    return {
        "state": observation.state,
        "stale": observation.stale,
        "reason": observation.reason,
        "progress": progress.__dict__ if progress is not None else None,
    }
