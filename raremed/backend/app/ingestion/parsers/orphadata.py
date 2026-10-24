"""Parse official Orphadata XML exports without inventing missing products."""

from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree as ET

from app.ingestion.frequency import normalize_frequency, polarity_from
from app.ingestion.identifiers import parse_identifier
from app.ingestion.inventory import peek_source_metadata
from app.ingestion.parsers.xml_util import attr, child, children, first_text, local_name, text_of, walk_named
from app.ingestion.records import Entity, Issue, Mapping, ParseResult, Relationship, Synonym


def parse_orphadata_xml(path: Path, *, role: str) -> ParseResult:
    version, release_date, schema_name, issues = peek_source_metadata(path, "orphadata", role)
    result = ParseResult(
        source="orphadata",
        file_path=str(path),
        role=role,
        version=version,
        release_date=release_date,
        schema_name=schema_name,
        issues=list(issues),
    )
    handlers = {
        "orphadata_diseases": _parse_product1,
        "orphadata_hpo_associations": _parse_product4,
        "orphadata_classifications": _parse_product3,
        "orphadata_genes": _parse_product6,
        "orphadata_disorder_associations": _parse_product7,
        "orphadata_epidemiology": _parse_product9,
    }
    handler = handlers.get(role)
    if handler is None:
        result.issues.append(
            Issue(
                code="orphadata_not_extracted",
                message=(
                    f"{path.name} was inspected ({schema_name or 'xml'}) but is not extracted "
                    "as disease-phenotype evidence."
                ),
                severity="info",
                source="orphadata",
                file_path=str(path),
            )
        )
        return result
    try:
        handler(path, result)
    except ET.ParseError as exc:
        result.issues.append(
            Issue(
                code="parse_failed",
                message=f"Orphadata XML parse failed for {path.name}: {exc}",
                severity="error",
                source="orphadata",
                file_path=str(path),
            )
        )
    if not result.entities and not result.relationships and not result.mappings:
        if not any(issue.code == "parse_failed" for issue in result.issues):
            result.issues.append(
                Issue(
                    code="schema_mismatch",
                    message=f"{path.name} did not match a known Orphadata {role} structure. No records were invented.",
                    severity="warning",
                    source="orphadata",
                    file_path=str(path),
                )
            )
    return result


def _parse_product1(path: Path, result: ParseResult) -> None:
    result.detected_fields = ["OrphaCode", "Name", "SynonymList", "ExternalReferenceList"]
    for _event, element in ET.iterparse(path, events=("end",)):
        if local_name(element.tag) != "Disorder":
            continue
        if child(element, "Disorder") is not None:
            continue
        entity = _disorder_entity(element, path, result)
        if entity is None:
            element.clear()
            continue
        result.entities.append(entity)
        result.mappings.extend(_external_references(element, entity.identifier, path, result))
        element.clear()


def _parse_product4(path: Path, result: ParseResult) -> None:
    result.detected_fields = ["OrphaCode", "HPOId", "HPOTerm", "HPOFrequency", "DiagnosticCriteria"]
    for _event, element in ET.iterparse(path, events=("end",)):
        if local_name(element.tag) != "HPODisorderSetStatus":
            continue
        associations = list(walk_named(element, "HPODisorderAssociation"))
        if not associations:
            element.clear()
            continue
        disorder = child(element, "Disorder")
        if disorder is None:
            disorder = element
        disease_id = _orpha_identifier(disorder)
        if disease_id is None:
            element.clear()
            continue
        label, labels = _names(disorder)
        result.entities.append(
            Entity(
                entity_type="disease",
                identifier=disease_id,
                label=label,
                labels_by_lang=labels,
                source="orphadata",
                source_file=path.name,
                source_version=result.version,
                source_release_date=result.release_date,
                source_record_id=attr(disorder, "id") or disease_id.curie,
                provenance={"from": "product4"},
            )
        )
        for association in associations:
            hpo_block = child(association, "HPO")
            hpo_id = first_text(association, "HPOId") or first_text(
                hpo_block if hpo_block is not None else association, "HPOId"
            )
            phenotype = parse_identifier(hpo_id or "")
            if phenotype is None:
                result.issues.append(
                    Issue(
                        code="unparsed_identifier",
                        message="Orphadata HPO association skipped because HPOId was not stable.",
                        severity="warning",
                        source="orphadata",
                        file_path=str(path),
                        subject=hpo_id,
                    )
                )
                continue
            frequency_el = child(association, "HPOFrequency")
            frequency_name = first_text(association, "HPOFrequency") or first_text(
                frequency_el if frequency_el is not None else association, "Name"
            )
            original, normalized = normalize_frequency(frequency_name)
            diagnostic = first_text(association, "DiagnosticCriteria")
            result.relationships.append(
                Relationship(
                    rel_type="has_phenotype",
                    subject=disease_id,
                    object=phenotype,
                    polarity=polarity_from(qualifier=None, frequency_normalized=normalized),
                    frequency=original,
                    frequency_normalized=normalized,
                    source="orphadata",
                    source_file=path.name,
                    source_version=result.version,
                    source_release_date=result.release_date,
                    source_record_id=attr(association, "id"),
                    provenance={
                        "hpo_term": first_text(association, "HPOTerm"),
                        "diagnostic_criteria": diagnostic,
                    },
                )
            )
        element.clear()


def _parse_product3(path: Path, result: ParseResult) -> None:
    result.detected_fields = ["OrphaCode", "Classification", "ClassificationNode"]
    for _event, element in ET.iterparse(path, events=("end",)):
        if local_name(element.tag) != "Classification":
            continue
        current_name = first_text(element, "Name")
        code = first_text(element, "OrphaNumber", "OrphaCode")
        current_id = parse_identifier(code, default_namespace="ORPHA") if code else None
        for disorder in walk_named(element, "Disorder"):
            identifier = _orpha_identifier(disorder)
            if identifier is None:
                continue
            label, labels = _names(disorder)
            result.entities.append(
                Entity(
                    entity_type="disease",
                    identifier=identifier,
                    label=label,
                    labels_by_lang=labels,
                    source="orphadata",
                    source_file=path.name,
                    source_version=result.version,
                    source_release_date=result.release_date,
                    source_record_id=attr(disorder, "id") or identifier.curie,
                    provenance={"from": "product3", "classification": current_name},
                )
            )
            if current_id is not None:
                result.relationships.append(
                    Relationship(
                        rel_type="classified_as",
                        subject=identifier,
                        object=current_id,
                        source="orphadata",
                        source_file=path.name,
                        source_version=result.version,
                        source_release_date=result.release_date,
                        source_record_id=attr(disorder, "id"),
                        qualifier=current_name,
                        provenance={"classification": current_name},
                    )
                )
        element.clear()


def _parse_product6(path: Path, result: ParseResult) -> None:
    result.detected_fields = ["OrphaCode", "Gene", "DisorderGeneAssociation"]
    for _event, element in ET.iterparse(path, events=("end",)):
        if local_name(element.tag) != "Disorder":
            continue
        associations = list(walk_named(element, "DisorderGeneAssociation"))
        if not associations:
            continue
        disease_id = _orpha_identifier(element)
        if disease_id is None:
            element.clear()
            continue
        for association in associations:
            gene = child(association, "Gene")
            symbol = first_text(gene, "Symbol") if gene is not None else None
            gene_id = None
            if gene is not None:
                for ref in walk_named(gene, "ExternalReference"):
                    source_name = first_text(ref, "Source")
                    reference = first_text(ref, "Reference")
                    if source_name and reference and source_name.upper() in {"HGNC", "ENSEMBL", "OMIM"}:
                        gene_id = parse_identifier(reference, default_namespace=source_name)
                        if gene_id:
                            break
            if gene_id is None and symbol:
                gene_id = parse_identifier(symbol, default_namespace="HGNC")
            if gene_id is None:
                continue
            result.entities.append(
                Entity(
                    entity_type="gene",
                    identifier=gene_id,
                    label=symbol or (first_text(gene, "Name") if gene is not None else None),
                    source="orphadata",
                    source_file=path.name,
                    source_version=result.version,
                    source_release_date=result.release_date,
                    source_record_id=attr(gene, "id") if gene is not None else gene_id.curie,
                )
            )
            result.relationships.append(
                Relationship(
                    rel_type="associated_gene",
                    subject=disease_id,
                    object=gene_id,
                    source="orphadata",
                    source_file=path.name,
                    source_version=result.version,
                    source_release_date=result.release_date,
                    source_record_id=attr(association, "id"),
                    qualifier=first_text(association, "DisorderGeneAssociationType"),
                    validation_status=first_text(association, "DisorderGeneAssociationStatus"),
                    evidence=first_text(association, "SourceOfValidation"),
                )
            )
        element.clear()


def _parse_product7(path: Path, result: ParseResult) -> None:
    result.detected_fields = ["OrphaCode", "DisorderDisorderAssociation", "TargetDisorder"]
    for _event, element in ET.iterparse(path, events=("end",)):
        if local_name(element.tag) != "Disorder":
            continue
        associations = list(walk_named(element, "DisorderDisorderAssociation"))
        if not associations:
            continue
        subject = _orpha_identifier(element)
        if subject is None:
            element.clear()
            continue
        for association in associations:
            target = child(association, "TargetDisorder")
            obj = _orpha_identifier(target) if target is not None else None
            if obj is None:
                continue
            result.relationships.append(
                Relationship(
                    rel_type="related_disorder",
                    subject=subject,
                    object=obj,
                    source="orphadata",
                    source_file=path.name,
                    source_version=result.version,
                    source_release_date=result.release_date,
                    source_record_id=attr(association, "id"),
                    qualifier=first_text(association, "DisorderDisorderAssociationType"),
                )
            )
        element.clear()


def _disorder_entity(element, path: Path, result: ParseResult) -> Entity | None:
    identifier = _orpha_identifier(element)
    if identifier is None:
        return None
    label, labels = _names(element)
    synonyms = []
    for item in walk_named(element, "Synonym"):
        value = text_of(item)
        if value:
            lang = attr(item, "lang")
            synonyms.append(Synonym(value=value, language=lang, scope="EXACT"))
            if lang and lang not in labels:
                labels[lang] = labels.get(lang, value)
    return Entity(
        entity_type="disease",
        identifier=identifier,
        label=label,
        synonyms=synonyms,
        labels_by_lang=labels,
        source="orphadata",
        source_file=path.name,
        source_version=result.version,
        source_release_date=result.release_date,
        source_record_id=attr(element, "id") or identifier.curie,
        provenance={"expert_link": first_text(element, "ExpertLink")},
    )


def _external_references(element, subject, path: Path, result: ParseResult) -> list[Mapping]:
    mappings: list[Mapping] = []
    for ref in walk_named(element, "ExternalReference"):
        source_name = first_text(ref, "Source")
        reference = first_text(ref, "Reference")
        if not source_name or not reference:
            continue
        target = parse_identifier(reference, default_namespace=source_name) or parse_identifier(
            f"{source_name}:{reference}"
        )
        if target is None:
            result.issues.append(
                Issue(
                    code="unparsed_identifier",
                    message=f"Orphadata xref {source_name}:{reference} was kept only as provenance.",
                    severity="info",
                    source="orphadata",
                    file_path=str(path),
                    subject=subject.curie,
                )
            )
            continue
        mappings.append(
            Mapping(
                subject=subject,
                object=target,
                mapping_relation=first_text(ref, "DisorderMappingRelation") or first_text(ref, "MappingRelation"),
                validation_status=first_text(ref, "DisorderMappingValidationStatus")
                or first_text(ref, "ValidationStatus"),
                source="orphadata",
                source_file=path.name,
                source_version=result.version,
                source_record_id=attr(ref, "id"),
                provenance={"source": source_name, "reference": reference},
            )
        )
    return mappings


def _parse_product9(path: Path, result: ParseResult) -> None:
    result.detected_fields = ["OrphaCode", "TypeOfInheritance", "AverageAgeOfOnset"]
    for _event, element in ET.iterparse(path, events=("end",)):
        if local_name(element.tag) != "Disorder":
            continue
        disease_id = _orpha_identifier(element)
        if disease_id is None:
            continue
        for item in walk_named(element, "TypeOfInheritance"):
            name = first_text(item, "Name") or text_of(item)
            record_id = attr(item, "id")
            if not name and not record_id:
                continue
            inheritance = parse_identifier(record_id or name, default_namespace="ORPHA-INH")
            if inheritance is None:
                continue
            result.entities.append(
                Entity(
                    entity_type="inheritance",
                    identifier=inheritance,
                    label=name,
                    labels_by_lang={"en": name} if name else {},
                    source="orphadata",
                    source_file=path.name,
                    source_version=result.version,
                    source_release_date=result.release_date,
                    source_record_id=record_id or inheritance.curie,
                    provenance={"from": "product9", "field": "TypeOfInheritance"},
                )
            )
            result.relationships.append(
                Relationship(
                    rel_type="has_inheritance",
                    subject=disease_id,
                    object=inheritance,
                    source="orphadata",
                    source_file=path.name,
                    source_version=result.version,
                    source_release_date=result.release_date,
                    source_record_id=record_id,
                    qualifier=name,
                    provenance={"from": "product9", "field": "TypeOfInheritance"},
                )
            )
        element.clear()


def _orpha_identifier(element) -> object | None:
    if element is None:
        return None
    code = first_text(element, "OrphaCode", "OrphaNumber", "ORPHAcode")
    if not code:
        return None
    return parse_identifier(code, default_namespace="ORPHA")


def _names(element) -> tuple[str | None, dict[str, str]]:
    labels: dict[str, str] = {}
    for item in children(element, "Name"):
        value = text_of(item)
        if not value:
            continue
        labels[attr(item, "lang") or "en"] = value
    label = labels.get("en") or next(iter(labels.values()), None)
    return label, labels
