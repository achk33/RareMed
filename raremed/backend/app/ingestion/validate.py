"""Validate extracted entities, mappings, and relationships."""

from __future__ import annotations

from app.ingestion.identifiers import DISEASE_NAMESPACES, PHENOTYPE_NAMESPACES
from app.ingestion.inventory import Inventory
from app.ingestion.records import Entity, Issue, Mapping, Relationship

VALID_POLARITY = {"present", "absent", "unknown"}


def validate_graph(
    *,
    inventory: Inventory,
    entities: list[Entity],
    relationships: list[Relationship],
    mappings: list[Mapping],
) -> list[Issue]:
    issues: list[Issue] = list(inventory.issues)
    by_curie = {item.identifier.curie: item for item in entities}
    parsed_namespaces = {item.identifier.namespace for item in entities}

    if inventory.missing_required:
        missing = ", ".join(f"{item.source}/{item.name}" for item in inventory.missing_required)
        issues.append(
            Issue(
                code="required_source_missing",
                message=f"Required source files are absent: {missing}",
                severity="error",
            )
        )

    for rel in relationships:
        if rel.rel_type == "has_phenotype":
            if rel.object.namespace not in PHENOTYPE_NAMESPACES:
                issues.append(
                    Issue(
                        code="invalid_phenotype_target",
                        message=f"has_phenotype target is not an HPO term: {rel.object.curie}",
                        severity="warning",
                        source=rel.source,
                        subject=rel.subject.curie,
                    )
                )
            if rel.subject.namespace not in DISEASE_NAMESPACES:
                issues.append(
                    Issue(
                        code="invalid_disease_subject",
                        message=f"has_phenotype subject is not a disease identifier: {rel.subject.curie}",
                        severity="warning",
                        source=rel.source,
                        subject=rel.subject.curie,
                    )
                )
            if rel.polarity not in VALID_POLARITY:
                issues.append(
                    Issue(
                        code="invalid_polarity",
                        message=f"Phenotype polarity must be present, absent, or unknown: {rel.polarity}",
                        severity="warning",
                        source=rel.source,
                        subject=rel.subject.curie,
                    )
                )
            if "HP" in parsed_namespaces and rel.object.curie not in by_curie:
                issues.append(
                    Issue(
                        code="unresolved_phenotype",
                        message=f"Phenotype {rel.object.curie} is not present in the parsed HPO file.",
                        severity="warning",
                        source=rel.source,
                        subject=rel.subject.curie,
                    )
                )
        if rel.subject.curie not in by_curie:
            issues.append(
                Issue(
                    code="dangling_subject",
                    message=f"Relationship {rel.rel_type} subject {rel.subject.curie} has no entity record.",
                    severity="info",
                    source=rel.source,
                    subject=rel.subject.curie,
                )
            )

    mondo_present = any(item.identifier.namespace == "MONDO" and item.source == "mondo" for item in entities)
    for mapping in mappings:
        if (
            mondo_present
            and mapping.object.namespace == "MONDO"
            and mapping.object.curie not in by_curie
        ):
            issues.append(
                Issue(
                    code="unresolved_xref",
                    message=f"{mapping.subject.curie} maps to {mapping.object.curie}, which is not in MONDO.",
                    severity="warning",
                    source=mapping.source,
                    file_path=mapping.source_file,
                    subject=mapping.subject.curie,
                )
            )
        if _looks_equivalent(mapping.mapping_relation) is False and mapping.mapping_relation:
            # Non-equivalent mappings must never be treated as identity. Record that fact.
            continue
    return issues


def _looks_equivalent(relation: str | None) -> bool | None:
    if not relation:
        return None
    token = relation.strip().lower()
    if token in {"e", "exact", "equivalent", "equivalent_to", "skos:exactmatch"}:
        return True
    if token.startswith("ntbt") or token.startswith("btnt") or token in {"nd", "narrow", "broad"}:
        return False
    return None
