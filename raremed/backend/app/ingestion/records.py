"""In-memory records produced by medical source parsers."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timezone
from typing import Any

from app.ingestion.identifiers import Identifier


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Synonym:
    value: str
    language: str | None = None
    scope: str | None = None
    synonym_type: str | None = None


@dataclass
class Issue:
    code: str
    message: str
    severity: str = "warning"
    source: str | None = None
    file_path: str | None = None
    subject: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Entity:
    entity_type: str
    identifier: Identifier
    label: str | None = None
    definition: str | None = None
    synonyms: list[Synonym] = field(default_factory=list)
    labels_by_lang: dict[str, str] = field(default_factory=dict)
    obsolete: bool = False
    replaced_by: list[str] = field(default_factory=list)
    alt_ids: list[str] = field(default_factory=list)
    source: str = ""
    source_file: str = ""
    source_version: str | None = None
    source_release_date: str | None = None
    source_record_id: str | None = None
    provenance: dict[str, Any] = field(default_factory=dict)

    @property
    def key(self) -> str:
        return self.identifier.curie


@dataclass
class Relationship:
    rel_type: str
    subject: Identifier
    object: Identifier
    polarity: str | None = None
    frequency: str | None = None
    frequency_normalized: str | None = None
    evidence: str | None = None
    qualifier: str | None = None
    onset: str | None = None
    sex: str | None = None
    aspect: str | None = None
    mapping_relation: str | None = None
    validation_status: str | None = None
    source: str = ""
    source_file: str = ""
    source_version: str | None = None
    source_release_date: str | None = None
    source_record_id: str | None = None
    provenance: dict[str, Any] = field(default_factory=dict)

    @property
    def key(self) -> tuple[str, ...]:
        return (
            self.rel_type,
            self.subject.curie,
            self.object.curie,
            self.polarity or "",
            self.source,
            self.source_record_id or "",
        )


@dataclass
class Mapping:
    subject: Identifier
    object: Identifier
    mapping_relation: str | None = None
    validation_status: str | None = None
    source: str = ""
    source_file: str = ""
    source_version: str | None = None
    source_record_id: str | None = None
    provenance: dict[str, Any] = field(default_factory=dict)

    @property
    def key(self) -> tuple[str, ...]:
        return (
            self.subject.curie,
            self.object.curie,
            self.mapping_relation or "",
            self.source,
            self.source_record_id or "",
        )


@dataclass
class ParseResult:
    source: str
    file_path: str
    role: str
    version: str | None = None
    release_date: str | None = None
    schema_name: str | None = None
    entities: list[Entity] = field(default_factory=list)
    relationships: list[Relationship] = field(default_factory=list)
    mappings: list[Mapping] = field(default_factory=list)
    issues: list[Issue] = field(default_factory=list)
    detected_fields: list[str] = field(default_factory=list)


def identifier_to_dict(identifier: Identifier) -> dict[str, Any]:
    return {
        "namespace": identifier.namespace,
        "local_id": identifier.local_id,
        "curie": identifier.curie,
        "original": identifier.original,
        "iri": identifier.iri,
    }


def record_to_dict(value: Any) -> Any:
    if isinstance(value, Identifier):
        return identifier_to_dict(value)
    if is_dataclass(value) and not isinstance(value, type):
        return {key: record_to_dict(item) for key, item in asdict(value).items()}
    if isinstance(value, list):
        return [record_to_dict(item) for item in value]
    if isinstance(value, dict):
        return {key: record_to_dict(item) for key, item in value.items()}
    return value
