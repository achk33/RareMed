"""Load Version 0.4 import records into the operational graph.

Missing variants and diagnostic tests are not invented. Inheritance is added
only from official Orphadata TypeOfInheritance records.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterator

from app.graph.records import EvidenceRecord, GraphEdge, GraphNode
from app.graph.schema import canonical_rel_type, kind_from_labels
from app.ingestion.inventory import inspect_inventory
from app.ingestion.parsers.orphadata import parse_orphadata_xml
from app.ingestion.pipeline import read_current_pointer


def iter_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line)
            if isinstance(payload, dict):
                yield payload


def load_import_records(imports_dir: Path) -> tuple[list[GraphNode], list[GraphEdge], list[EvidenceRecord], list[str]]:
    nodes_path = imports_dir / "nodes.jsonl"
    edges_path = imports_dir / "edges.jsonl"
    warnings: list[str] = []
    if not nodes_path.is_file() or not edges_path.is_file():
        raise FileNotFoundError(f"Import records are missing under {imports_dir}")

    nodes: dict[str, GraphNode] = {}
    for row in iter_jsonl(nodes_path):
        curie = str(row.get("id") or "")
        if not curie:
            warnings.append("Skipped a node without a stable identifier.")
            continue
        kind = kind_from_labels([str(item) for item in row.get("labels") or []])
        props = dict(row.get("properties") or {})
        props["curie"] = curie
        props["kind"] = kind
        if curie in nodes and nodes[curie].kind != kind:
            warnings.append(f"Refused to merge {curie} from {nodes[curie].kind} into {kind}.")
            continue
        nodes[curie] = GraphNode(curie=curie, kind=kind, properties=props)

    edges: list[GraphEdge] = []
    evidence: list[EvidenceRecord] = []
    seen_edges: set[str] = set()
    for row in iter_jsonl(edges_path):
        rel_type = canonical_rel_type(str(row.get("type") or ""))
        start = str(row.get("start") or "")
        end = str(row.get("end") or "")
        edge_id = str(row.get("id") or "")
        if not rel_type or not start or not end or not edge_id:
            warnings.append("Skipped an edge that lacked type or identifiers.")
            continue
        if start not in nodes or end not in nodes:
            warnings.append(f"Skipped {rel_type} {start}->{end}: missing endpoint.")
            continue
        if edge_id in seen_edges:
            continue
        seen_edges.add(edge_id)
        props = dict(row.get("properties") or {})
        props["id"] = edge_id
        props["inferred"] = False
        polarity = props.get("polarity")
        if rel_type == "HAS_PHENOTYPE" and polarity not in {"present", "absent", "unknown"}:
            props["polarity"] = "unknown"
        edges.append(
            GraphEdge(id=edge_id, type=rel_type, start=start, end=end, inferred=False, properties=props)
        )
        evidence.append(
            EvidenceRecord(
                id=edge_id,
                subject=start,
                object=end,
                rel_type=rel_type,
                source=props.get("source"),
                source_file=props.get("source_file"),
                source_version=props.get("source_version"),
                source_release_date=props.get("source_release_date"),
                source_record_id=props.get("source_record_id"),
                evidence=props.get("evidence"),
                polarity=props.get("polarity"),
                frequency=props.get("frequency"),
                inferred=False,
            )
        )
    return list(nodes.values()), edges, evidence, warnings


def enrich_official_inheritance(
    data_root: Path,
    nodes: list[GraphNode],
    edges: list[GraphEdge],
    evidence: list[EvidenceRecord],
) -> tuple[list[GraphNode], list[GraphEdge], list[EvidenceRecord], list[str]]:
    if any(edge.type == "HAS_INHERITANCE" for edge in edges):
        return nodes, edges, evidence, []
    inventory = inspect_inventory(data_root)
    warnings: list[str] = []
    by_curie = {node.curie: node for node in nodes}
    seen = {edge.id for edge in edges}
    for item in inventory.files:
        if item.role != "orphadata_epidemiology" or not item.present:
            continue
        if "ages" not in item.name.lower() and "product9" not in item.name.lower():
            continue
        parsed = parse_orphadata_xml(item.path, role="orphadata_epidemiology")
        for entity in parsed.entities:
            if entity.entity_type != "inheritance":
                continue
            curie = entity.identifier.curie
            if curie not in by_curie:
                by_curie[curie] = GraphNode(
                    curie=curie,
                    kind="InheritancePattern",
                    properties={
                        "curie": curie,
                        "kind": "InheritancePattern",
                        "label": entity.label,
                        "namespace": entity.identifier.namespace,
                        "local_id": entity.identifier.local_id,
                        "original": entity.identifier.original,
                        "source": entity.source,
                        "source_file": entity.source_file,
                        "source_version": entity.source_version,
                        "source_release_date": entity.source_release_date,
                        "source_record_id": entity.source_record_id,
                    },
                )
        for rel in parsed.relationships:
            if rel.rel_type != "has_inheritance":
                continue
            edge_id = "|".join(rel.key)
            if edge_id in seen:
                continue
            if rel.subject.curie not in by_curie:
                warnings.append(f"Inheritance for unknown disease {rel.subject.curie} was skipped.")
                continue
            if rel.object.curie not in by_curie:
                continue
            seen.add(edge_id)
            props = {
                "id": edge_id,
                "inferred": False,
                "source": rel.source,
                "source_file": rel.source_file,
                "source_version": rel.source_version,
                "source_release_date": rel.source_release_date,
                "source_record_id": rel.source_record_id,
                "qualifier": rel.qualifier,
            }
            edges.append(
                GraphEdge(
                    id=edge_id,
                    type="HAS_INHERITANCE",
                    start=rel.subject.curie,
                    end=rel.object.curie,
                    inferred=False,
                    properties=props,
                )
            )
            evidence.append(
                EvidenceRecord(
                    id=edge_id,
                    subject=rel.subject.curie,
                    object=rel.object.curie,
                    rel_type="HAS_INHERITANCE",
                    source=rel.source,
                    source_file=rel.source_file,
                    source_version=rel.source_version,
                    source_release_date=rel.source_release_date,
                    source_record_id=rel.source_record_id,
                    inferred=False,
                )
            )
        warnings.extend(issue.message for issue in parsed.issues if issue.severity != "info")
    return list(by_curie.values()), edges, evidence, warnings


def resolve_imports_dir(data_root: Path, run_id: str | None = None) -> Path:
    if run_id:
        path = data_root / "imports" / "runs" / run_id
        if path.is_dir():
            return path
        raise FileNotFoundError(f"Import run {run_id} was not found.")
    pointer = read_current_pointer(data_root)
    if pointer and pointer.get("imports_dir"):
        path = Path(str(pointer["imports_dir"]))
        if path.is_dir():
            return path
    current = data_root / "imports" / "current.json"
    if current.is_file():
        payload = json.loads(current.read_text(encoding="utf-8"))
        if payload.get("imports_dir"):
            path = Path(str(payload["imports_dir"]))
            if path.is_dir():
                return path
    raise FileNotFoundError("No Version 0.4 import records are available to load.")


def prepare_graph_payload(data_root: Path, run_id: str | None = None) -> dict[str, Any]:
    imports_dir = resolve_imports_dir(data_root, run_id)
    nodes, edges, evidence, warnings = load_import_records(imports_dir)
    nodes, edges, evidence, extra = enrich_official_inheritance(data_root, nodes, edges, evidence)
    warnings.extend(extra)
    manifest = {}
    manifest_path = imports_dir / "manifest.json"
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    return {
        "imports_dir": str(imports_dir),
        "dataset_run_id": manifest.get("run_id") or imports_dir.name,
        "nodes": nodes,
        "edges": edges,
        "evidence": evidence,
        "warnings": warnings,
        "manifest": manifest,
    }
