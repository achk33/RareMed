"""Medical dataset ingestion: discover, validate, parse, normalize, export."""

from __future__ import annotations

import uuid
from collections import Counter
from pathlib import Path
from typing import Any, Callable

from app.ingestion.errors import MissingRequiredSourcesError
from app.ingestion.export import export_run, write_json
from app.ingestion.inventory import Inventory, SourceFile, inspect_inventory
from app.ingestion.mapping import (
    ambiguous_mapping_issues,
    mapping_relationships,
    mappings_from_relationships,
    stub_entities_for_mappings,
)
from app.ingestion.normalize import merge_entities, merge_mappings, merge_relationships
from app.ingestion.parsers.hpoa import parse_hpoa
from app.ingestion.parsers.obo_json import parse_obo_graphs_json
from app.ingestion.parsers.obo_text import parse_obo_text
from app.ingestion.parsers.orphadata import parse_orphadata_xml
from app.ingestion.parsers.owl import parse_owl
from app.ingestion.records import Entity, Issue, Mapping, ParseResult, Relationship, utc_now
from app.ingestion.validate import validate_graph

Parser = Callable[[SourceFile], ParseResult]


class IngestionPipeline:
    def __init__(self, data_root: Path, *, strict: bool = False) -> None:
        self.data_root = data_root.resolve()
        self.strict = strict

    def inspect(self) -> Inventory:
        return inspect_inventory(self.data_root)

    def run(self, *, run_id: str | None = None) -> dict[str, Any]:
        run_id = run_id or uuid.uuid4().hex
        inventory = self.inspect()
        if not inventory.readable:
            raise FileNotFoundError(f"Data root is not readable: {self.data_root}")

        missing = [f"{item.source}/{item.name}" for item in inventory.missing_required]
        if self.strict and missing:
            raise MissingRequiredSourcesError(missing)

        parseable = [item for item in inventory.files if item.present and _is_parseable(item)]
        if not parseable:
            raise MissingRequiredSourcesError(missing or ["no parseable medical source files"])

        results = [self._parse_file(item) for item in parseable]
        entities: list[Entity] = []
        relationships: list[Relationship] = []
        mappings: list[Mapping] = []
        issues: list[Issue] = list(inventory.issues)
        for result in results:
            entities.extend(result.entities)
            relationships.extend(result.relationships)
            mappings.extend(result.mappings)
            issues.extend(result.issues)

        mappings.extend(mappings_from_relationships(relationships))
        entities.extend(stub_entities_for_mappings(mappings, entities))
        entities, merge_issues = merge_entities(entities)
        issues.extend(merge_issues)
        mappings = merge_mappings(mappings)
        relationships.extend(mapping_relationships(mappings))
        relationships = merge_relationships(relationships)
        issues.extend(ambiguous_mapping_issues(mappings))
        issues.extend(
            validate_graph(
                inventory=inventory,
                entities=entities,
                relationships=relationships,
                mappings=mappings,
            )
        )

        counts = _counts(entities, relationships, mappings, issues)
        source_summaries = _source_summaries(inventory, results, entities, relationships, issues)
        processed_dir = self.data_root / "processed" / "runs" / run_id
        imports_dir = self.data_root / "imports" / "runs" / run_id
        inventory_payload = {
            "data_root": str(self.data_root),
            "missing_required": missing,
            "files": [_file_payload(item) for item in inventory.files],
        }
        manifest = export_run(
            processed_dir=processed_dir,
            imports_dir=imports_dir,
            run_id=run_id,
            entities=entities,
            relationships=relationships,
            mappings=mappings,
            issues=issues,
            counts=counts,
            inventory_payload=inventory_payload,
            source_summaries=source_summaries,
        )
        pointer = {
            "run_id": run_id,
            "created_at": utc_now().isoformat(),
            "status": "succeeded",
            "processed_dir": str(processed_dir),
            "imports_dir": str(imports_dir),
            "counts": counts,
            "missing_required": missing,
        }
        write_json(self.data_root / "processed" / "current.json", pointer)
        write_json(self.data_root / "imports" / "current.json", pointer)
        return {
            "run_id": run_id,
            "status": "succeeded",
            "strict": self.strict,
            "processed_dir": str(processed_dir),
            "imports_dir": str(imports_dir),
            "counts": counts,
            "missing_required": missing,
            "sources": source_summaries,
            "warnings": [item.to_dict() for item in issues],
            "manifest": manifest,
            "raw_files_modified": False,
        }

    def _parse_file(self, item: SourceFile) -> ParseResult:
        parser = _parser_for(item)
        if parser is None:
            return ParseResult(
                source=item.source,
                file_path=str(item.path),
                role=item.role,
                version=item.version,
                release_date=item.release_date,
                schema_name=item.schema_name,
                issues=[
                    Issue(
                        code="unsupported_source_format",
                        message=f"{item.name} was found but has no parser for role {item.role}.",
                        severity="warning",
                        source=item.source,
                        file_path=item.relative_path,
                    )
                ],
            )
        return parser(item)


def read_current_pointer(data_root: Path) -> dict[str, Any] | None:
    path = data_root / "processed" / "current.json"
    if not path.is_file():
        return None
    try:
        import json

        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def list_run_ids(data_root: Path) -> list[str]:
    directory = data_root / "processed" / "runs"
    if not directory.is_dir():
        return []
    return sorted(path.name for path in directory.iterdir() if path.is_dir())


def rollback_current(data_root: Path, previous_run_id: str) -> dict[str, Any]:
    processed = data_root / "processed" / "runs" / previous_run_id
    imports = data_root / "imports" / "runs" / previous_run_id
    if not processed.is_dir() or not (processed / "manifest.json").is_file():
        raise FileNotFoundError(f"Previous import {previous_run_id} is not available for rollback.")
    import json

    manifest = json.loads((processed / "manifest.json").read_text(encoding="utf-8"))
    pointer = {
        "run_id": previous_run_id,
        "created_at": utc_now().isoformat(),
        "status": "succeeded",
        "processed_dir": str(processed),
        "imports_dir": str(imports),
        "counts": manifest.get("counts") or {},
        "rolled_back_to": previous_run_id,
    }
    write_json(data_root / "processed" / "current.json", pointer)
    write_json(data_root / "imports" / "current.json", pointer)
    return pointer


def _parser_for(item: SourceFile) -> Parser | None:
    suffix = item.path.suffix.lower()
    if item.role == "hpo_disease_annotations" or suffix == ".hpoa":
        return lambda source: parse_hpoa(source.path, source=source.source, role=source.role)
    if item.source == "orphadata" and suffix == ".xml":
        return lambda source: parse_orphadata_xml(source.path, role=source.role)
    prefixes, entity_type = _ontology_target(item.source)
    if prefixes is None:
        return None
    if suffix == ".json":
        return lambda source: parse_obo_graphs_json(
            source.path,
            source=source.source,
            role=source.role,
            allowed_prefixes=prefixes,
            entity_type=entity_type,
        )
    if suffix == ".obo":
        return lambda source: parse_obo_text(
            source.path,
            source=source.source,
            role=source.role,
            allowed_prefixes=prefixes,
            entity_type=entity_type,
        )
    if suffix == ".owl":
        return lambda source: parse_owl(
            source.path,
            source=source.source,
            role=source.role,
            allowed_prefixes=prefixes,
            entity_type=entity_type,
        )
    return None


def _ontology_target(source: str) -> tuple[tuple[str, ...], str] | tuple[None, None]:
    if source == "hpo":
        return ("HP",), "phenotype"
    if source == "mondo":
        return ("MONDO",), "disease"
    return None, None


def _is_parseable(item: SourceFile) -> bool:
    if item.role.endswith("_other") and item.source == "orphadata":
        return False
    return item.path.suffix.lower() in {".json", ".obo", ".owl", ".hpoa", ".xml"}


def _counts(
    entities: list[Entity],
    relationships: list[Relationship],
    mappings: list[Mapping],
    issues: list[Issue],
) -> dict[str, Any]:
    return {
        "entities": len(entities),
        "entities_by_type": dict(Counter(item.entity_type for item in entities)),
        "relationships": len(relationships),
        "relationships_by_type": dict(Counter(item.rel_type for item in relationships)),
        "mappings": len(mappings),
        "warnings": sum(1 for item in issues if item.severity != "info"),
        "issues": len(issues),
    }


def _source_summaries(
    inventory: Inventory,
    results: list[ParseResult],
    entities: list[Entity],
    relationships: list[Relationship],
    issues: list[Issue],
) -> list[dict[str, Any]]:
    by_file = {result.file_path: result for result in results}
    summaries: list[dict[str, Any]] = []
    for item in inventory.files:
        result = by_file.get(str(item.path))
        file_issues = [issue for issue in issues if issue.file_path in {item.relative_path, str(item.path), item.name}]
        if not item.present:
            status = "missing"
        elif result and (result.entities or result.relationships or result.mappings):
            status = "parsed"
        elif result and any(issue.severity == "error" for issue in result.issues):
            status = "failed"
        elif item.present and _is_parseable(item):
            status = "parsed" if result else "failed"
        else:
            status = "skipped"
        entity_counts = dict(Counter(entity.entity_type for entity in (result.entities if result else [])))
        rel_counts = dict(Counter(rel.rel_type for rel in (result.relationships if result else [])))
        summaries.append(
            {
                "source": item.source,
                "role": item.role,
                "file_path": item.relative_path if item.present else None,
                "expected_path": item.relative_path,
                "version": (result.version if result else None) or item.version,
                "release_date": (result.release_date if result else None) or item.release_date,
                "import_status": status,
                "entity_counts": entity_counts,
                "relationship_counts": rel_counts,
                "validation_warnings": [
                    issue.message for issue in (result.issues if result else item.issues) + file_issues
                ][:50],
                "required": item.required,
                "schema_name": (result.schema_name if result else None) or item.schema_name,
            }
        )
    return summaries


def _file_payload(item: SourceFile) -> dict[str, Any]:
    return {
        "source": item.source,
        "role": item.role,
        "name": item.name,
        "relative_path": item.relative_path,
        "present": item.present,
        "required": item.required,
        "size_bytes": item.size_bytes,
        "version": item.version,
        "release_date": item.release_date,
        "schema_name": item.schema_name,
    }
