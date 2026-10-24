"""CLI for medical dataset inspection, import, status, and rollback."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.core.config import get_settings
from app.core.database import get_session_factory
from app.ingestion.errors import IngestionConflictError, MissingRequiredSourcesError
from app.ingestion.pipeline import IngestionPipeline, read_current_pointer
from app.ingestion.store import execute_rollback, execute_run, history


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="RareMed medical dataset ingestion")
    parser.add_argument("--data-root", type=Path, default=None, help="Override data/ directory")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("inspect", help="List source files, versions, and missing required names")
    run = sub.add_parser("run", help="Parse sources and export processed and import records")
    run.add_argument("--strict", action="store_true", help="Fail when hp.obo or phenotype.hpoa is absent")
    run.add_argument("--skip-db", action="store_true", help="Write files only; do not record the run in PostgreSQL")
    sub.add_parser("status", help="Show the current import pointer and recent runs")
    sub.add_parser("rollback", help="Restore the previous successful import pointer")
    args = parser.parse_args(argv)
    data_root = (args.data_root or get_settings().data_root).resolve()

    if args.command == "inspect":
        return _inspect(data_root)
    if args.command == "run":
        return _run(data_root, strict=args.strict, skip_db=args.skip_db)
    if args.command == "status":
        return _status(data_root)
    if args.command == "rollback":
        return _rollback(data_root)
    return 2


def _inspect(data_root: Path) -> int:
    inventory = IngestionPipeline(data_root).inspect()
    rows = []
    for item in inventory.files:
        rows.append(
            {
                "source": item.source,
                "file": item.relative_path if item.present else item.name,
                "present": item.present,
                "required": item.required,
                "version": item.version,
                "release_date": item.release_date,
                "schema": item.schema_name,
                "bytes": item.size_bytes,
            }
        )
    payload = {
        "data_root": str(data_root),
        "readable": inventory.readable,
        "missing_required": [f"{item.source}/{item.name}" for item in inventory.missing_required],
        "files": rows,
        "issues": [item.to_dict() for item in inventory.issues],
    }
    print(json.dumps(payload, indent=2, default=str))
    return 0 if inventory.readable else 1


def _run(data_root: Path, *, strict: bool, skip_db: bool) -> int:
    session = None if skip_db else _optional_session()
    try:
        payload = execute_run(data_root, session=session, strict=strict, trigger="cli")
    except MissingRequiredSourcesError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except IngestionConflictError as exc:
        print(str(exc), file=sys.stderr)
        return 3
    finally:
        if session is not None:
            session.close()
    print(json.dumps({key: payload[key] for key in payload if key != "warnings"}, indent=2, default=str))
    print(f"warnings: {len(payload.get('warnings') or [])}", file=sys.stderr)
    return 0


def _status(data_root: Path) -> int:
    pointer = read_current_pointer(data_root)
    session = _optional_session()
    rows = []
    try:
        rows = [
            {
                "run_id": item.run_key,
                "status": item.status,
                "entities": item.entity_count,
                "relationships": item.relationship_count,
                "created_at": item.created_at,
            }
            for item in history(session)
        ]
    finally:
        if session is not None:
            session.close()
    print(json.dumps({"current": pointer, "history": rows}, indent=2, default=str))
    return 0


def _rollback(data_root: Path) -> int:
    session = _optional_session()
    try:
        pointer = execute_rollback(data_root, session=session)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    finally:
        if session is not None:
            session.close()
    print(json.dumps(pointer, indent=2, default=str))
    return 0


def _optional_session():
    try:
        return get_session_factory()()
    except Exception:
        return None


if __name__ == "__main__":
    raise SystemExit(main())
