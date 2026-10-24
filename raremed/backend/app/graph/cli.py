"""CLI for loading and inspecting the operational knowledge graph."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.core.config import get_settings
from app.graph.jobs import GraphConflictError, GraphImportError, load_graph, rollback_graph
from app.graph.neo4j import probe_neo4j
from app.graph.jobs import get_graph_store


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="RareMed operational knowledge graph")
    parser.add_argument("--data-root", type=Path, default=None)
    sub = parser.add_subparsers(dest="command", required=True)
    load = sub.add_parser("load", help="Load Version 0.4 import records into Neo4j")
    load.add_argument("--dataset-run", default=None)
    sub.add_parser("stats", help="Print graph statistics")
    sub.add_parser("rollback", help="Roll back the current graph import")
    args = parser.parse_args(argv)
    data_root = (args.data_root or get_settings().data_root).resolve()
    if args.command == "load":
        return _load(data_root, args.dataset_run)
    if args.command == "stats":
        return _stats()
    if args.command == "rollback":
        return _rollback()
    return 2


def _load(data_root: Path, dataset_run: str | None) -> int:
    try:
        payload = load_graph(data_root, dataset_run_id=dataset_run)
    except (GraphImportError, GraphConflictError, FileNotFoundError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps(payload, indent=2, default=str))
    return 0


def _stats() -> int:
    probe = probe_neo4j()
    if probe.status != "ok":
        print(json.dumps({"loaded": False, "connection": probe.model_dump()}, indent=2))
        return 1
    stats = get_graph_store().stats()
    print(
        json.dumps(
            {
                "loaded": stats.loaded,
                "run_id": stats.run_id,
                "node_counts": stats.node_counts,
                "relationship_counts": stats.relationship_counts,
                "evidence_count": stats.evidence_count,
                "inferred_relationship_count": stats.inferred_relationship_count,
            },
            indent=2,
        )
    )
    return 0


def _rollback() -> int:
    try:
        payload = rollback_graph()
    except (GraphImportError, FileNotFoundError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps(payload, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
