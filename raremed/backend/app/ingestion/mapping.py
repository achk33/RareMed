"""Cross-source identifier mappings. Distinct concepts are never collapsed."""

from __future__ import annotations

from collections import defaultdict

from app.ingestion.identifiers import STUB_NAMESPACES, entity_type_for
from app.ingestion.records import Entity, Issue, Mapping, Relationship


def mappings_from_relationships(relationships: list[Relationship]) -> list[Mapping]:
    mappings: list[Mapping] = []
    for item in relationships:
        if item.rel_type != "xref":
            continue
        mappings.append(
            Mapping(
                subject=item.subject,
                object=item.object,
                mapping_relation=item.mapping_relation,
                validation_status=item.validation_status,
                source=item.source,
                source_file=item.source_file,
                source_version=item.source_version,
                source_record_id=item.source_record_id,
                provenance=item.provenance,
            )
        )
    return mappings


def stub_entities_for_mappings(mappings: list[Mapping], entities: list[Entity]) -> list[Entity]:
    known = {item.identifier.curie for item in entities}
    stubs: list[Entity] = []
    for mapping in mappings:
        for identifier in (mapping.subject, mapping.object):
            if identifier.curie in known:
                continue
            known.add(identifier.curie)
            stubs.append(
                Entity(
                    entity_type=entity_type_for(identifier),
                    identifier=identifier,
                    source=mapping.source,
                    source_file=mapping.source_file,
                    source_version=mapping.source_version,
                    source_record_id=identifier.curie,
                    provenance={"stub": identifier.namespace in STUB_NAMESPACES, "from": "mapping"},
                )
            )
    return stubs


def mapping_relationships(mappings: list[Mapping]) -> list[Relationship]:
    relationships: list[Relationship] = []
    for item in mappings:
        relationships.append(
            Relationship(
                rel_type="xref",
                subject=item.subject,
                object=item.object,
                mapping_relation=item.mapping_relation,
                validation_status=item.validation_status,
                source=item.source,
                source_file=item.source_file,
                source_version=item.source_version,
                source_record_id=item.source_record_id,
                provenance=item.provenance,
            )
        )
    return relationships


def ambiguous_mapping_issues(mappings: list[Mapping]) -> list[Issue]:
    grouped: dict[tuple[str, str], set[str]] = defaultdict(set)
    source_for: dict[tuple[str, str], Mapping] = {}
    for item in mappings:
        key = (item.subject.curie, item.object.namespace)
        grouped[key].add(item.object.curie)
        source_for[key] = item
    issues: list[Issue] = []
    for (subject, namespace), objects in grouped.items():
        if len(objects) < 2:
            continue
        sample = source_for[(subject, namespace)]
        issues.append(
            Issue(
                code="ambiguous_mapping",
                message=(
                    f"{subject} maps to multiple {namespace} concepts "
                    f"({', '.join(sorted(objects))}). Mappings were kept and not merged."
                ),
                severity="warning",
                source=sample.source,
                file_path=sample.source_file,
                subject=subject,
            )
        )
    return issues
