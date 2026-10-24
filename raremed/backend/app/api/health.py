from fastapi import APIRouter

from app.core.constants import APP_VERSION, DECISION_SUPPORT_NOTICE, SERVICE_NAME
from app.schemas.health import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Liveness probe. It does not check PostgreSQL, Neo4j, or Ollama."""
    return HealthResponse(
        status="ok",
        service=SERVICE_NAME,
        version=APP_VERSION,
        role="decision-support",
    )


@router.get("/api/v1/health", response_model=HealthResponse, include_in_schema=False)
def health_v1() -> HealthResponse:
    return health()
