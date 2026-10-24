from fastapi import APIRouter

from app.schemas.status import StatusResponse
from app.services.status import collect_status

router = APIRouter(tags=["status"])


@router.get("/status", response_model=StatusResponse)
def status() -> StatusResponse:
    """Dependency report. Individual outages stay inside the payload."""
    return collect_status()
