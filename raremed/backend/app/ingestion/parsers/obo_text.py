"""Parse OBO text stanzas for HPO and MONDO."""

from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path

from app.ingestion.identifiers import parse_identifier
from app.ingestion.inventory import peek_source_metadata
from app.ingestion.records import Entity, Issue, Mapping, ParseResult, Relationship, Synonym

STANZA_HEADER = re.compile(r"^\[(.+)]$")
TAG_LINE = re.compile(r"^([^:!]+):\s*(.*)$")
QUOTED = re.compile(r'^"((?:\\.|[^"\\])*)"(?:\s+(EXACT|RELATED|BROAD|NARROW))?(?:\s+\S.*)?$')


def parse_obo_text(
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
        schema_name=schema_name or "obo_text",
        issues=list(issues),
        detected_fields=["id", "name", "def", "synonym", "is_a", "xref", "alt_id"],
    )
    allowed = {item.upper() for item in allowed_prefixes}
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        result.issues.append(
            Issue(
                code="parse_failed",
                message=f"Could not read {path.name}: {exc}",
                severity="error",
                source=source,
                file_path=str(path),
            )
        )
        return result

    header, stanzas = _split_stanzas(text)
    if not result.version:
        result.version = _header_value(header, "data-version")
    if not result.release_date:
        result.release_date = _header_value(header, "date") or result.version

    for kind, fields in stanzas:
        if kind.lower() != "term":
            continue
        identifier = parse_identifier(_first(fields, "id") or "")
        if identifier is None or identifier.namespace not in allowed:
            continue
        name = _first(fields, "name")
        definition = _unquote(_first(fields, "def"))
        synonyms = [_synonym(value) for value in fields.get("synonym", [])]
        synonyms = [item for item in synonyms if item]
        labels = {"en": name} if name else {}
        result.entities.append(
            Entity(
                entity_type=entity_type,
                identifier=identifier,
                label=name,
                definition=definition,
                synonyms=synonyms,
                labels_by_lang=labels,
                obsolete=_truthy(_first(fields, "is_obsolete")),
                replaced_by=[value.split("!")[0].strip() for value in fields.get("replaced_by", [])],
                alt_ids=[value.split("!")[0].strip() for value in fields.get("alt_id", [])],
                source=source,
                source_file=path.name,
                source_version=result.version,
                source_release_date=result.release_date,
                source_record_id=identifier.curie,
                provenance={"stanza": "Term"},
            )
        )
        for xref in fields.get("xref", []):
            target = parse_identifier(xref.split("!")[0].strip())
            if target is None or target.curie == identifier.curie:
                continue
            result.mappings.append(
                Mapping(
                    subject=identifier,
                    object=target,
                    mapping_relation="xref",
                    source=source,
                    source_file=path.name,
                    source_version=result.version,
                    source_record_id=identifier.curie,
                    provenance={"original": xref},
                )
            )
        for parent in fields.get("is_a", []):
            obj = parse_identifier(parent.split("!")[0].strip())
            if obj is None or obj.namespace not in allowed:
                continue
            result.relationships.append(
                Relationship(
                    rel_type="is_a",
                    subject=identifier,
                    object=obj,
                    source=source,
                    source_file=path.name,
                    source_version=result.version,
                    source_release_date=result.release_date,
                    source_record_id=f"{identifier.curie}|is_a|{obj.curie}",
                    provenance={"original": parent},
                )
            )
    if not result.entities and "[Term]" not in text:
        result.issues.append(
            Issue(
                code="schema_mismatch",
                message=f"{path.name} is not an OBO term file.",
                severity="error",
                source=source,
                file_path=str(path),
            )
        )
    return result


def _split_stanzas(text: str) -> tuple[dict[str, list[str]], list[tuple[str, dict[str, list[str]]]]]:
    header: dict[str, list[str]] = {}
    stanzas: list[tuple[str, dict[str, list[str]]]] = []
    current_kind: str | None = None
    current: dict[str, list[str]] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("!"):
            continue
        stanza = STANZA_HEADER.match(line)
        if stanza:
            if current_kind:
                stanzas.append((current_kind, current))
            current_kind = stanza.group(1)
            current = {}
            continue
        match = TAG_LINE.match(line)
        if not match:
            continue
        tag = match.group(1).strip()
        value = match.group(2).strip()
        if current_kind is None:
            header.setdefault(tag, []).append(value)
        else:
            current.setdefault(tag, []).append(value)
    if current_kind:
        stanzas.append((current_kind, current))
    return header, stanzas


def _header_value(header: dict[str, list[str]], key: str) -> str | None:
    values = header.get(key)
    return values[0].strip() if values else None


def _first(fields: dict[str, list[str]], key: str) -> str | None:
    values = fields.get(key)
    return values[0].strip() if values else None


def _unquote(value: str | None) -> str | None:
    if not value:
        return None
    match = QUOTED.match(value)
    if match:
        return match.group(1).replace('\\"', '"')
    return value


def _synonym(value: str) -> Synonym | None:
    match = QUOTED.match(value)
    if not match:
        text = value.strip()
        return Synonym(value=text) if text else None
    return Synonym(value=match.group(1).replace('\\"', '"'), scope=match.group(2))


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"true", "1", "yes"}
