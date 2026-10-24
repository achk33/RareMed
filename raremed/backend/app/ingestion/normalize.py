"""Merge parsed records onto stable identifiers without collapsing distinct concepts."""

from __future__ import annotations

from app.ingestion.records import Entity, Issue, Mapping, Relationship, Synonym


def merge_entities(entities: list[Entity]) -> tuple[list[Entity], list[Issue]]:
    merged: dict[str, Entity] = {}
    issues: list[Issue] = []
    for entity in entities:
        key = entity.identifier.curie
        existing = merged.get(key)
        if existing is None:
            merged[key] = entity
            continue
        if existing.entity_type != entity.entity_type:
            issues.append(
                Issue(
                    code="conflicting_entity_type",
                    message=(
                        f"{key} was seen as {existing.entity_type} and {entity.entity_type}. "
                        "The first type was kept; records were not merged into a new concept."
                    ),
                    severity="warning",
                    source=entity.source,
                    subject=key,
                )
            )
        merged[key] = _merge_entity(existing, entity)
    return list(merged.values()), issues


def merge_relationships(relationships: list[Relationship]) -> list[Relationship]:
    merged: dict[tuple[str, ...], Relationship] = {}
    for item in relationships:
        existing = merged.get(item.key)
        if existing is None:
            merged[item.key] = item
            continue
        existing.provenance = {**existing.provenance, **item.provenance}
        if item.frequency and not existing.frequency:
            existing.frequency = item.frequency
            existing.frequency_normalized = item.frequency_normalized
        if item.evidence and not existing.evidence:
            existing.evidence = item.evidence
    return list(merged.values())


def merge_mappings(mappings: list[Mapping]) -> list[Mapping]:
    merged: dict[tuple[str, ...], Mapping] = {}
    for item in mappings:
        existing = merged.get(item.key)
        if existing is None:
            merged[item.key] = item
            continue
        existing.provenance = {**existing.provenance, **item.provenance}
        if item.validation_status and not existing.validation_status:
            existing.validation_status = item.validation_status
    return list(merged.values())


def _merge_entity(left: Entity, right: Entity) -> Entity:
    synonyms = _unique_synonyms(left.synonyms + right.synonyms)
    labels = {**left.labels_by_lang, **right.labels_by_lang}
    sources = [item for item in (left.source, right.source) if item]
    files = [item for item in (left.source_file, right.source_file) if item]
    return Entity(
        entity_type=left.entity_type,
        identifier=left.identifier,
        label=left.label or right.label,
        definition=left.definition or right.definition,
        synonyms=synonyms,
        labels_by_lang=labels,
        obsolete=left.obsolete or right.obsolete,
        replaced_by=_unique(left.replaced_by + right.replaced_by),
        alt_ids=_unique(left.alt_ids + right.alt_ids),
        source="+".join(dict.fromkeys(sources)),
        source_file=";".join(dict.fromkeys(files)),
        source_version=left.source_version or right.source_version,
        source_release_date=left.source_release_date or right.source_release_date,
        source_record_id=left.source_record_id or right.source_record_id,
        provenance={
            **left.provenance,
            **right.provenance,
            "merged_sources": list(dict.fromkeys(sources)),
            "originals": [
                left.identifier.original,
                right.identifier.original,
            ],
        },
    )


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(item for item in values if item))


def _unique_synonyms(values: list[Synonym]) -> list[Synonym]:
    seen: set[tuple[str, str | None, str | None]] = set()
    unique: list[Synonym] = []
    for item in values:
        key = (item.value, item.language, item.scope)
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique
