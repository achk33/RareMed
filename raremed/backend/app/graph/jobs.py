"""Load and roll back operational graph import jobs."""

from __future__ import annotations

import threading
import uuid
from typing import Any

from app.graph.loader import prepare_graph_payload
from app.graph.memory import InMemoryGraphStore
from app.graph.neo4j import Neo4jGraphStore, probe_neo4j
from app.graph.store import GraphStore

_LOCK = threading.Lock()
_RUNNING = False
_MEMORY = InMemoryGraphStore()
_USE_MEMORY = False


class GraphImportError(RuntimeError):
    pass


class GraphConflictError(RuntimeError):
    pass


def is_running() -> bool:
    return _RUNNING


def use_memory_store(enabled: bool = True) -> InMemoryGraphStore:
    global _USE_MEMORY
    _USE_MEMORY = enabled
    return _MEMORY


def get_graph_store() -> GraphStore:
    if _USE_MEMORY:
        return _MEMORY
    probe = probe_neo4j()
    if probe.status != "ok":
        raise GraphImportError("Neo4j is not available.")
    return Neo4jGraphStore()


def load_graph(data_root, *, dataset_run_id: str | None = None, store: GraphStore | None = None) -> dict[str, Any]:
    global _RUNNING
    if not _LOCK.acquire(blocking=False):
        raise GraphConflictError("A graph import is already running.")
    _RUNNING = True
    run_id = uuid.uuid4().hex
    target = store or get_graph_store()
    try:
        payload = prepare_graph_payload(data_root, dataset_run_id)
        previous = None
        try:
            current = target.current_import()
            previous = current.get("run_id") if current else None
        except Exception:
            previous = None
        target.mark_import(run_id, "running", dataset_run_id=payload["dataset_run_id"], previous_run_id=previous)
        try:
            target.load_batch(
                run_id=run_id,
                nodes=payload["nodes"],
                edges=payload["edges"],
                evidence=payload["evidence"],
                dataset_run_id=payload["dataset_run_id"],
                previous_run_id=previous,
            )
        except Exception:
            try:
                target.rollback_run(run_id)
                target.mark_import(run_id, "failed", previous_run_id=previous)
            except Exception:
                pass
            raise
        stats = target.stats()
        return {
            "run_id": run_id,
            "status": "succeeded",
            "dataset_run_id": payload["dataset_run_id"],
            "imports_dir": payload["imports_dir"],
            "node_count": len(payload["nodes"]),
            "relationship_count": len(payload["edges"]),
            "evidence_count": len(payload["evidence"]),
            "inferred_relationship_count": 0,
            "warnings": payload["warnings"][:100],
            "stats": {
                "node_counts": stats.node_counts,
                "relationship_counts": stats.relationship_counts,
            },
        }
    finally:
        _RUNNING = False
        _LOCK.release()


def rollback_graph(store: GraphStore | None = None) -> dict[str, Any]:
    target = store or get_graph_store()
    current = target.current_import()
    if not current:
        raise FileNotFoundError("No graph import is available to roll back.")
    removed = target.rollback_run(str(current["run_id"]))
    return {"rolled_back": current["run_id"], "removed": removed, "current": target.current_import()}
