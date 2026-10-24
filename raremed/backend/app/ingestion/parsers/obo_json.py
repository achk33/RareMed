"""Parse OBO Graphs JSON exports (HPO and MONDO)."""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from app.ingestion.identifiers import Identifier, parse_identifier
from app.ingestion.inventory import peek_source_metadata
from app.ingestion.records import Entity, Issue, Mapping, ParseResult, Relationship, Synonym

ALLOWED_NODE_TYPES = {"CLASS", "class"}
PRED_ISA = {
    "is_a",
    "http://www.w3.org/2000/01/rdf-schema#subClassOf",
    "rdfs:subClassOf",
}
ALT_ID_PREDS = {
    "http://www.geneontology.org/formats/oboInOwl#hasAlternativeId",
    "http://www.geneontology.org/formats/oboInOwl#hasAlternativeID",
    "oboInOwl:hasAlternativeId",
    "hasAlternativeId",
}
REPLACED_BY_PREDS = {
    "http://purl.obolibrary.org/obo/IAO_0100001",
    "IAO:0100001",
    "replaced_by",
}
XREF_PREDS = {
    "http://www.geneontology.org/formats/oboInOwl#hasDbXref",
    "oboInOwl:hasDbXref",
    "hasDbXref",
}


def parse_obo_graphs_json(
    path: Path,
    *,
    source: str,
    role: str,
    allowed_prefixes: Iterable[str],
    entity_type: str,
) -> ParseResult:
    version, release_date, schema_name, issues = peek_source_metadata(path, source, role)
    result = ParseResult(
        source=source,
        file_path=str(path),
        role=role,
        version=version,
        release_date=release_date,
        schema_name=schema_name or "obo_graphs_json",
        issues=list(issues),
        detected_fields=["id", "lbl", "type", "meta"],
    )
    allowed = {item.upper() for item in allowed_prefixes}

    try:
        nodes, edges = _load_nodes_and_edges(path)
    except (OSError, json.JSONDecodeError, ImportError) as exc:
        result.issues.append(
            Issue(
                code="parse_failed",
                message=f"Could not parse {path.name}: {exc}",
                severity="error",
                source=source,
                file_path=str(path),
            )
        )
        return result

    if not nodes and not edges:
        result.issues.append(
            Issue(
                code="schema_mismatch",
                message=f"{path.name} has no OBO Graphs nodes.",
                severity="error",
                source=source,
                file_path=str(path),
            )
        )
        return result

    result.release_date = result.release_date or result.version
    for node in nodes:
        if not isinstance(node, dict):
            continue
        entity = _node_entity(
            node,
            allowed=allowed,
            entity_type=entity_type,
            source=source,
            path=path,
            version=result.version,
            release_date=result.release_date,
        )
        if entity is None:
            continue
        result.entities.append(entity)
        result.mappings.extend(_node_xrefs(node, entity.identifier, source, path, result.version))
    for edge in edges:
        if not isinstance(edge, dict):
            continue
        relationship = _edge_relationship(
            edge,
            allowed=allowed,
            source=source,
            path=path,
            version=result.version,
            release_date=result.release_date,
        )
        if relationship is not None:
            result.relationships.append(relationship)
    return result


def _load_nodes_and_edges(path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    try:
        import ijson  # type: ignore

        with path.open("rb") as handle:
            nodes = [item for item in ijson.items(handle, "graphs.item.nodes.item") if isinstance(item, dict)]
        with path.open("rb") as handle:
            edges = [item for item in ijson.items(handle, "graphs.item.edges.item") if isinstance(item, dict)]
        if nodes or edges:
            return nodes, edges
    except ImportError:
        pass
    except Exception:
        pass
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return [], []
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    for graph in payload.get("graphs") or []:
        if not isinstance(graph, dict):
            continue
        nodes.extend(item for item in graph.get("nodes") or [] if isinstance(item, dict))
        edges.extend(item for item in graph.get("edges") or [] if isinstance(item, dict))
    return nodes, edges


def _node_entity(
    node: dict[str, Any],
    *,
    allowed: set[str],
    entity_type: str,
    source: str,
    path: Path,
    version: str | None,
    release_date: str | None,
) -> Entity | None:
    node_type = str(node.get("type") or "")
    if node_type and node_type not in ALLOWED_NODE_TYPES:
        return None
    identifier = parse_identifier(str(node.get("id") or ""))
    if identifier is None or identifier.namespace not in allowed:
        return None
    meta = node.get("meta") if isinstance(node.get("meta"), dict) else {}
    definition = None
    definition_block = meta.get("definition")
    if isinstance(definition_block, dict):
        definition = _clean(definition_block.get("val"))
    elif isinstance(definition_block, str):
        definition = _clean(definition_block)
    synonyms = [_synonym(item) for item in meta.get("synonyms") or [] if isinstance(item, dict)]
    synonyms = [item for item in synonyms if item is not None]
    alt_ids = [
        value
        for value in _property_values(meta, ALT_ID_PREDS)
        if value
    ]
    replaced = [value for value in _property_values(meta, REPLACED_BY_PREDS) if value]
    labels_by_lang: dict[str, str] = {}
    label = _clean(node.get("lbl"))
    if label:
        labels_by_lang["en"] = label
    return Entity(
        entity_type=entity_type,
        identifier=identifier,
        label=label,
        definition=definition,
        synonyms=synonyms,
        labels_by_lang=labels_by_lang,
        obsolete=bool(meta.get("deprecated")),
        replaced_by=replaced,
        alt_ids=alt_ids,
        source=source,
        source_file=path.name,
        source_version=version,
        source_release_date=release_date,
        source_record_id=identifier.curie,
        provenance={"node_type": node_type or None, "json_id": node.get("id")},
    )


def _node_xrefs(
    node: dict[str, Any],
    subject: Identifier,
    source: str,
    path: Path,
    version: str | None,
) -> list[Mapping]:
    meta = node.get("meta") if isinstance(node.get("meta"), dict) else {}
    mappings: list[Mapping] = []
    xrefs = list(meta.get("xrefs") or [])
    for item in xrefs:
        value = item.get("val") if isinstance(item, dict) else item
        target = parse_identifier(str(value or ""))
        if target is None or target.curie == subject.curie:
            continue
        mappings.append(
            Mapping(
                subject=subject,
                object=target,
                mapping_relation="hasDbXref",
                source=source,
                source_file=path.name,
                source_version=version,
                source_record_id=subject.curie,
                provenance={"original": value},
            )
        )
    for value in _property_values(meta, XREF_PREDS):
        target = parse_identifier(value)
        if target is None or target.curie == subject.curie:
            continue
        mappings.append(
            Mapping(
                subject=subject,
                object=target,
                mapping_relation="hasDbXref",
                source=source,
                source_file=path.name,
                source_version=version,
                source_record_id=subject.curie,
                provenance={"original": value},
            )
        )
    return mappings


def _edge_relationship(
    edge: dict[str, Any],
    *,
    allowed: set[str],
    source: str,
    path: Path,
    version: str | None,
    release_date: str | None,
) -> Relationship | None:
    subject = parse_identifier(str(edge.get("sub") or ""))
    obj = parse_identifier(str(edge.get("obj") or ""))
    pred = str(edge.get("pred") or "")
    if subject is None or obj is None:
        return None
    if subject.namespace not in allowed or obj.namespace not in allowed:
        return None
    rel_type = "is_a" if pred in PRED_ISA or pred.endswith("#subClassOf") else "ontology_edge"
    return Relationship(
        rel_type=rel_type,
        subject=subject,
        object=obj,
        source=source,
        source_file=path.name,
        source_version=version,
        source_release_date=release_date,
        source_record_id=f"{subject.curie}|{pred}|{obj.curie}",
        provenance={"pred": pred},
    )


def _synonym(item: dict[str, Any]) -> Synonym | None:
    value = _clean(item.get("val"))
    if not value:
        return None
    pred = str(item.get("pred") or "")
    scope = pred.replace("has", "").replace("Synonym", "").strip() or None
    if pred.endswith("ExactSynonym"):
        scope = "EXACT"
    elif pred.endswith("RelatedSynonym"):
        scope = "RELATED"
    elif pred.endswith("BroadSynonym"):
        scope = "BROAD"
    elif pred.endswith("NarrowSynonym"):
        scope = "NARROW"
    return Synonym(value=value, language=None, scope=scope, synonym_type=_clean(item.get("synonymType")))


def _property_values(meta: dict[str, Any], preds: set[str]) -> list[str]:
    values: list[str] = []
    for item in meta.get("basicPropertyValues") or []:
        if not isinstance(item, dict):
            continue
        pred = str(item.get("pred") or "")
        if pred in preds or pred.split("#")[-1] in {token.split("#")[-1] for token in preds}:
            value = _clean(item.get("val"))
            if value:
                values.append(value)
    return values


def _meta_version(graph: dict[str, Any], meta: dict[str, Any]) -> str | None:
    graph_id = str(graph.get("id") or "")
    match = None
    if "releases/" in graph_id:
        match = graph_id.split("releases/", 1)[1].split("/", 1)[0]
        if match:
            return match
    for item in meta.get("basicPropertyValues") or []:
        if not isinstance(item, dict):
            continue
        if str(item.get("pred") or "").endswith("versionInfo"):
            return _clean(item.get("val"))
    return _clean(graph.get("version"))


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
