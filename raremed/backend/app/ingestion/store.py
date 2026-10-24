"""Persist import-run history when a database is available."""

from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.ingestion.errors import IngestionConflictError
from app.ingestion.pipeline import IngestionPipeline, list_run_ids, read_current_pointer, rollback_current
from app.models.ingestion import IngestionRun

_RUN_LOCK = threading.Lock()
_RUNNING = False


def is_running() -> bool:
    return _RUNNING


def save_run(session: Session | None, payload: dict[str, Any]) -> None:
    if session is None:
        return
    row = session.query(IngestionRun).filter(IngestionRun.run_key == payload["run_id"]).one_or_none()
    if row is None:
        row = IngestionRun(id=uuid.uuid4(), run_key=payload["run_id"])
        session.add(row)
    row.status = payload.get("status") or "succeeded"
    row.trigger = payload.get("trigger") or "cli"
    row.strict = bool(payload.get("strict"))
    row.processed_dir = payload.get("processed_dir")
    row.imports_dir = payload.get("imports_dir")
    row.previous_run_key = payload.get("previous_run_id")
    counts = payload.get("counts") or {}
    row.entity_count = int(counts.get("entities") or 0)
    row.relationship_count = int(counts.get("relationships") or 0)
    row.warning_count = int(counts.get("warnings") or 0)
    row.missing_required = payload.get("missing_required") or []
    row.source_summaries = payload.get("sources") or []
    row.counts = counts
    row.warnings = (payload.get("warnings") or [])[:200]
    row.error_message = payload.get("error_message")
    if payload.get("status") in {"succeeded", "failed", "rolled_back"}:
        row.finished_at = datetime.now(timezone.utc)
    session.commit()


def history(session: Session | None) -> list[IngestionRun]:
    if session is None:
        return []
    return session.query(IngestionRun).order_by(IngestionRun.created_at.desc()).limit(20).all()


def last_successful(session: Session | None) -> IngestionRun | None:
    if session is None:
        return None
    return (
        session.query(IngestionRun)
        .filter(IngestionRun.status == "succeeded")
        .order_by(IngestionRun.created_at.desc())
        .first()
    )


def execute_run(
    data_root,
    *,
    session: Session | None,
    strict: bool = False,
    trigger: str = "cli",
) -> dict[str, Any]:
    global _RUNNING
    if not _RUN_LOCK.acquire(blocking=False):
        raise IngestionConflictError("An import is already running.")
    _RUNNING = True
    previous = read_current_pointer(data_root)
    try:
        payload = IngestionPipeline(data_root, strict=strict).run()
        payload["trigger"] = trigger
        payload["previous_run_id"] = previous.get("run_id") if previous else None
        save_run(session, payload)
        return payload
    except Exception as exc:
        failed = {
            "run_id": uuid.uuid4().hex,
            "status": "failed",
            "trigger": trigger,
            "strict": strict,
            "error_message": str(exc),
            "missing_required": getattr(exc, "missing", []),
            "counts": {},
            "sources": [],
            "warnings": [],
            "previous_run_id": previous.get("run_id") if previous else None,
        }
        try:
            save_run(session, failed)
        except Exception:
            pass
        raise
    finally:
        _RUNNING = False
        _RUN_LOCK.release()


def execute_rollback(data_root, *, session: Session | None) -> dict[str, Any]:
    current = read_current_pointer(data_root)
    if current is None:
        raise FileNotFoundError("No successful import is available to roll back.")
    previous_id = current.get("run_id")
    candidates = [item for item in reversed(list_run_ids(data_root)) if item != previous_id]
    if session is not None:
        rows = (
            session.query(IngestionRun)
            .filter(IngestionRun.status == "succeeded", IngestionRun.run_key != previous_id)
            .order_by(IngestionRun.created_at.desc())
            .all()
        )
        if rows:
            candidates = [rows[0].run_key]
    if not candidates:
        raise FileNotFoundError("No previous successful import is available for recovery.")
    pointer = rollback_current(data_root, candidates[0])
    if session is not None and previous_id:
        row = session.query(IngestionRun).filter(IngestionRun.run_key == previous_id).one_or_none()
        if row is not None:
            row.status = "rolled_back"
            session.commit()
    save_run(
        session,
        {
            "run_id": pointer["run_id"],
            "status": "succeeded",
            "trigger": "rollback",
            "processed_dir": pointer.get("processed_dir"),
            "imports_dir": pointer.get("imports_dir"),
            "counts": pointer.get("counts") or {},
            "sources": [],
            "warnings": [],
            "missing_required": [],
        },
    )
    return pointer
