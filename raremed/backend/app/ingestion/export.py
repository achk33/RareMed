"""Write processed artifacts and import-ready graph records. Never writes to data/raw."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from app.ingestion.records import Entity, Issue, Mapping, Relationship, identifier_to_dict, record_to_dict, utc_now


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, default=str))
            handle.write("\n")
            count += 1
    return count


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def entity_row(entity: Entity) -> dict[str, Any]:
    return record_to_dict(entity)


def relationship_row(item: Relationship) -> dict[str, Any]:
    return record_to_dict(item)


def mapping_row(item: Mapping) -> dict[str, Any]:
    return record_to_dict(item)


def graph_node(entity: Entity) -> dict[str, Any]:
    labels = {
        "phenotype": ["Phenotype"],
        "disease": ["Disease"],
        "gene": ["Gene"],
        "identifier": ["Identifier"],
        "inheritance": ["InheritancePattern"],
        "variant": ["Variant"],
        "test": ["DiagnosticTest"],
    }.get(entity.entity_type, ["Entity"])
    return {
        "id": entity.identifier.curie,
        "labels": labels,
        "properties": {
            "curie": entity.identifier.curie,
            "namespace": entity.identifier.namespace,
            "local_id": entity.identifier.local_id,
            "original": entity.identifier.original,
            "iri": entity.identifier.iri,
            "label": entity.label,
            "definition": entity.definition,
            "synonyms": [item.value for item in entity.synonyms],
            "labels_by_lang": entity.labels_by_lang,
            "obsolete": entity.obsolete,
            "alt_ids": entity.alt_ids,
            "source": entity.source,
            "source_file": entity.source_file,
            "source_version": entity.source_version,
            "source_release_date": entity.source_release_date,
            "source_record_id": entity.source_record_id,
        },
    }


def graph_edge(item: Relationship) -> dict[str, Any]:
    edge_id = "|".join(item.key)
    return {
        "id": edge_id,
        "type": item.rel_type.upper(),
        "start": item.subject.curie,
        "end": item.object.curie,
        "properties": {
            "polarity": item.polarity,
            "frequency": item.frequency,
            "frequency_normalized": item.frequency_normalized,
            "evidence": item.evidence,
            "qualifier": item.qualifier,
            "onset": item.onset,
            "mapping_relation": item.mapping_relation,
            "validation_status": item.validation_status,
            "source": item.source,
            "source_file": item.source_file,
            "source_version": item.source_version,
            "source_release_date": item.source_release_date,
            "source_record_id": item.source_record_id,
        },
    }


def export_run(
    *,
    processed_dir: Path,
    imports_dir: Path,
    run_id: str,
    entities: list[Entity],
    relationships: list[Relationship],
    mappings: list[Mapping],
    issues: list[Issue],
    counts: dict[str, Any],
    inventory_payload: dict[str, Any],
    source_summaries: list[dict[str, Any]],
) -> dict[str, Any]:
    write_jsonl(processed_dir / "entities.jsonl", (entity_row(item) for item in entities))
    write_jsonl(processed_dir / "relationships.jsonl", (relationship_row(item) for item in relationships))
    write_jsonl(processed_dir / "mappings.jsonl", (mapping_row(item) for item in mappings))
    write_jsonl(processed_dir / "warnings.jsonl", (item.to_dict() for item in issues))
    write_json(processed_dir / "counts.json", counts)
    write_json(processed_dir / "inventory.json", inventory_payload)
    write_jsonl(imports_dir / "nodes.jsonl", (graph_node(item) for item in entities))
    write_jsonl(imports_dir / "edges.jsonl", (graph_edge(item) for item in relationships))
    created = utc_now().isoformat()
    manifest = {
        "run_id": run_id,
        "created_at": created,
        "counts": counts,
        "sources": source_summaries,
        "raw_files_modified": False,
        "note": "Relationships come only from downloaded source files. Missing associations were not invented.",
    }
    write_json(processed_dir / "manifest.json", manifest)
    write_json(imports_dir / "manifest.json", {**manifest, "kind": "graph_import"})
    return manifest
