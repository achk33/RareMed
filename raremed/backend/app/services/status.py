"""Aggregate dependency status without failing the request when one is down."""

import logging
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import create_engine

from app.ai.model_config import load_model_config
from app.ai.ollama import OllamaClient
from app.core.config import get_settings
from app.core.constants import API_VERSION, APP_VERSION, DECISION_SUPPORT_NOTICE, SERVICE_NAME
from app.core.database import check_database, driver_connect_args
from app.graph.neo4j import probe_neo4j
from app.ingestion.discovery import discover_sources
from app.schemas.common import DependencyStatus
from app.schemas.graph import GraphStatus
from app.schemas.status import DatasetSummary, OllamaStatus, StatusResponse

logger = logging.getLogger("raremed.status")

GRAPH_NOTE = (
    "Version 0.6 explores asserted HPO, Orphadata, and MONDO relations from Neo4j. "
    "Missing associations are not invented."
)


def collect_status() -> StatusResponse:
    settings = get_settings()
    with ThreadPoolExecutor(max_workers=3) as pool:
        database_future = pool.submit(_probe_database)
        neo4j_future = pool.submit(probe_neo4j)
        ollama_future = pool.submit(_probe_ollama)
        database = database_future.result()
        neo4j = neo4j_future.result()
        ollama = ollama_future.result()

    report = discover_sources(settings.data_root)
    sources_with_files = [source.source for source in report.sources if source.file_count > 0]
    total_files = sum(source.file_count for source in report.sources)
    return StatusResponse(
        service=SERVICE_NAME,
        version=APP_VERSION,
        api_version=API_VERSION,
        environment=settings.app_env,
        decision_support_notice=DECISION_SUPPORT_NOTICE,
        database=database,
        neo4j=neo4j,
        ollama=ollama,
        datasets=DatasetSummary(
            readable=report.readable,
            total_files=total_files,
            sources_with_files=sources_with_files,
        ),
        clinical_reasoning_enabled=False,
    )


def collect_graph_status() -> GraphStatus:
    from app.graph.jobs import get_graph_store, is_running
    from app.graph.jobs import GraphImportError

    connection = probe_neo4j()
    try:
        stats = get_graph_store().stats()
        return GraphStatus(
            connection=connection,
            loaded=stats.loaded,
            note=stats.note or GRAPH_NOTE,
            run_id=stats.run_id,
            dataset_run_id=stats.dataset_run_id,
            node_counts=stats.node_counts,
            relationship_counts=stats.relationship_counts,
            evidence_count=stats.evidence_count,
            inferred_relationship_count=stats.inferred_relationship_count,
            running=is_running(),
        )
    except GraphImportError:
        return GraphStatus(connection=connection, loaded=False, note=GRAPH_NOTE, running=is_running())


def _probe_database() -> DependencyStatus:
    settings = get_settings()
    engine = create_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=1,
        max_overflow=0,
        connect_args=driver_connect_args(settings.database_url),
    )
    try:
        check_database(engine)
        return DependencyStatus(status="ok", detail=None)
    except Exception as exc:
        logger.warning("database probe failed", extra={"error_type": exc.__class__.__name__})
        return DependencyStatus(status="unavailable", detail=exc.__class__.__name__)
    finally:
        engine.dispose()


def _probe_ollama() -> OllamaStatus:
    settings = get_settings()
    config = load_model_config(settings)
    return OllamaClient(settings.ollama_base_url, settings.ollama_timeout_seconds).probe(
        config.model,
        think=config.think,
    )


