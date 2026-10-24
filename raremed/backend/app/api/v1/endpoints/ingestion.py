from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_staff
from app.core.config import get_settings
from app.core.errors import AppError
from app.ingestion.errors import IngestionConflictError, MissingRequiredSourcesError
from app.ingestion.inventory import inspect_inventory
from app.ingestion.pipeline import read_current_pointer
from app.ingestion.store import execute_rollback, execute_run, history, is_running, last_successful
from app.models import User
from app.schemas.ingestion import IngestionRunRequest, IngestionRunSummary, IngestionStatus, SourceImportRow

router = APIRouter(prefix="/ingestion", tags=["ingestion"])

NOTE = (
    "Version 0.4 imports HPO, Orphadata, and MONDO files from data/raw. "
    "Raw downloads are never overwritten, and missing associations are not invented."
)


@router.get("/status", response_model=IngestionStatus)
def ingestion_status(
    _: User = Depends(require_staff),
    session: Session = Depends(get_db),
) -> IngestionStatus:
    settings = get_settings()
    inventory = inspect_inventory(settings.data_root)
    rows = history(session)
    successful = last_successful(session)
    current = read_current_pointer(settings.data_root)
    current_summary = None
    if current:
        match = next((item for item in rows if item.run_key == current.get("run_id")), None)
        current_summary = (
            _row_summary(match)
            if match
            else IngestionRunSummary(
                run_id=str(current.get("run_id")),
                status=str(current.get("status") or "succeeded"),
                entity_count=int((current.get("counts") or {}).get("entities") or 0),
                relationship_count=int((current.get("counts") or {}).get("relationships") or 0),
                missing_required=list(current.get("missing_required") or []),
            )
        )
    sources = []
    summaries = (successful.source_summaries if successful else None) or []
    by_path = {item.get("expected_path"): item for item in summaries if isinstance(item, dict)}
    for item in inventory.files:
        stored = by_path.get(item.relative_path) or {}
        sources.append(
            SourceImportRow(
                source=item.source,
                role=item.role,
                file_path=item.relative_path if item.present else None,
                expected_path=item.relative_path,
                version=stored.get("version") or item.version,
                release_date=stored.get("release_date") or item.release_date,
                import_status=stored.get("import_status")
                or ("missing" if not item.present else "discovered"),
                entity_counts=stored.get("entity_counts") or {},
                relationship_counts=stored.get("relationship_counts") or {},
                validation_warnings=stored.get("validation_warnings")
                or [issue.message for issue in item.issues],
                last_successful_import=successful.finished_at if successful and stored else None,
                required=item.required,
                schema_name=stored.get("schema_name") or item.schema_name,
            )
        )
    return IngestionStatus(
        running=is_running(),
        current_run=current_summary,
        last_successful_import=successful.finished_at if successful else None,
        missing_required=[f"{item.source}/{item.name}" for item in inventory.missing_required],
        sources=sources,
        history=[_row_summary(item) for item in rows],
        counts=(successful.counts if successful else {}) or (current or {}).get("counts") or {},
        note=NOTE,
    )


@router.post("/run", response_model=IngestionStatus)
def run_ingestion(
    body: IngestionRunRequest,
    _: User = Depends(require_staff),
    session: Session = Depends(get_db),
) -> IngestionStatus:
    try:
        execute_run(get_settings().data_root, session=session, strict=body.strict, trigger="api")
    except IngestionConflictError as exc:
        raise AppError("ingestion_running", str(exc), 409) from exc
    except MissingRequiredSourcesError as exc:
        raise AppError("required_source_missing", str(exc), 400) from exc
    except FileNotFoundError as exc:
        raise AppError("data_root_missing", str(exc), 400) from exc
    return ingestion_status(_, session)


@router.post("/rollback", response_model=IngestionStatus)
def rollback_ingestion(
    _: User = Depends(require_staff),
    session: Session = Depends(get_db),
) -> IngestionStatus:
    try:
        execute_rollback(get_settings().data_root, session=session)
    except FileNotFoundError as exc:
        raise AppError("ingestion_rollback_unavailable", str(exc), 400) from exc
    return ingestion_status(_, session)


def _row_summary(row) -> IngestionRunSummary:
    return IngestionRunSummary(
        run_id=row.run_key,
        status=row.status,
        trigger=row.trigger,
        created_at=row.created_at,
        finished_at=row.finished_at,
        entity_count=row.entity_count,
        relationship_count=row.relationship_count,
        warning_count=row.warning_count,
        missing_required=list(row.missing_required or []),
        error_message=row.error_message,
    )
