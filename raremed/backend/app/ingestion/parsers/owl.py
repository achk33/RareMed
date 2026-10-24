"""Conservative OWL/RDF parser for official HPO and MONDO exports."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from xml.etree import ElementTree as ET

from app.ingestion.identifiers import parse_identifier
from app.ingestion.inventory import peek_source_metadata
from app.ingestion.parsers.xml_util import attr, children, local_name, text_of
from app.ingestion.records import Entity, Issue, Mapping, ParseResult, Relationship, Synonym


def parse_owl(
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
        schema_name=schema_name,
        issues=list(issues),
        detected_fields=["rdf:about", "rdfs:label", "rdfs:subClassOf"],
    )
    header = path.read_bytes()[:2048].decode("utf-8", "replace")
    if "Prefix(" in header or "Ontology(" in header:
        result.issues.append(
            Issue(
                code="unsupported_owl_syntax",
                message=f"{path.name} looks like OWL functional syntax, which is not parsed.",
                severity="error",
                source=source,
                file_path=str(path),
            )
        )
        return result
    if "<rdf:RDF" not in header and "<RDF" not in header and "rdf:RDF" not in header:
        result.issues.append(
            Issue(
                code="unsupported_owl_syntax",
                message=f"{path.name} is not RDF/XML OWL. No classes were invented.",
                severity="error",
                source=source,
                file_path=str(path),
            )
        )
        return result

    allowed = {item.upper() for item in allowed_prefixes}
    try:
        for event, element in ET.iterparse(path, events=("end",)):
            if local_name(element.tag) != "Class":
                continue
            about = attr(element, "about", "ID")
            identifier = parse_identifier(about or "")
            if identifier is None or identifier.namespace not in allowed:
                element.clear()
                continue
            labels = _labels(element)
            label = labels.get("en") or next(iter(labels.values()), None)
            synonyms = [
                Synonym(value=text, scope="EXACT")
                for item in children(element, "hasExactSynonym")
                if (text := text_of(item))
            ]
            obsolete = any(text_of(item) == "true" for item in children(element, "deprecated"))
            result.entities.append(
                Entity(
                    entity_type=entity_type,
                    identifier=identifier,
                    label=label,
                    definition=text_of(next(iter(children(element, "IAO_0000115")), None)),
                    synonyms=synonyms,
                    labels_by_lang=labels,
                    obsolete=obsolete,
                    source=source,
                    source_file=path.name,
                    source_version=result.version,
                    source_release_date=result.release_date,
                    source_record_id=identifier.curie,
                    provenance={"rdf_about": about},
                )
            )
            for xref in children(element, "hasDbXref"):
                target = parse_identifier(text_of(xref) or "")
                if target is None:
                    continue
                result.mappings.append(
                    Mapping(
                        subject=identifier,
                        object=target,
                        mapping_relation="hasDbXref",
                        source=source,
                        source_file=path.name,
                        source_version=result.version,
                        source_record_id=identifier.curie,
                    )
                )
            for parent in children(element, "subClassOf"):
                resource = attr(parent, "resource")
                obj = parse_identifier(resource or "")
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
                    )
                )
            element.clear()
    except ET.ParseError as exc:
        result.issues.append(
            Issue(
                code="parse_failed",
                message=f"OWL XML parse failed for {path.name}: {exc}",
                severity="error",
                source=source,
                file_path=str(path),
            )
        )
    return result


def _labels(element) -> dict[str, str]:
    labels: dict[str, str] = {}
    for item in children(element, "label"):
        value = text_of(item)
        if not value:
            continue
        lang = None
        for key, raw in item.attrib.items():
            if key.endswith("lang"):
                lang = raw
        labels[lang or "en"] = value
    return labels
