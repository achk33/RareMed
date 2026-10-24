from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.constants import API_VERSION, APP_VERSION, DECISION_SUPPORT_NOTICE, SERVICE_NAME
from app.core.database import dispose_engine, get_session_factory
from app.core.errors import register_exception_handlers
from app.core.logging import RequestContextMiddleware, configure_logging

configure_logging()


@asynccontextmanager
async def lifespan(_: FastAPI):
    configure_logging()
    try:
        session = get_session_factory()()
        from app.services.auth import AuthService

        AuthService(session).seed_admin()
        session.close()
    except Exception:
        logger = __import__("logging").getLogger("raremed.auth")
        logger.warning("admin seed skipped", extra={"error_type": "StartupError"})
    yield
    dispose_engine()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="RareMed AI",
        version=APP_VERSION,
        summary="Clinical decision-support foundation. Not a diagnostic device.",
        description=(
            f"{DECISION_SUPPORT_NOTICE} "
            "Version 0.6 explores asserted medical relations in a bounded Neo4j graph. "
            "It does not rank diseases or present answers as verified diagnoses."
        ),
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Accept", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
    )
    register_exception_handlers(app)
    app.include_router(health_router)
    app.include_router(api_router, prefix=f"/api/{API_VERSION}")

    @app.get("/", include_in_schema=False)
    def root() -> dict[str, str]:
        return {
            "service": SERVICE_NAME,
            "version": APP_VERSION,
            "role": "decision-support",
            "health": "/health",
            "status": "/api/v1/status",
            "docs": "/docs",
        }

    return app


app = create_app()
