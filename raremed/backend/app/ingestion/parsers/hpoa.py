"""Parse HPO disease-phenotype annotation files (phenotype.hpoa)."""

from __future__ import annotations

from pathlib import Path

from app.ingestion.frequency import normalize_frequency, polarity_from
from app.ingestion.identifiers import parse_identifier
from app.ingestion.inventory import peek_source_metadata
from app.ingestion.records import Entity, Issue, ParseResult, Relationship

REQUIRED_COLUMNS = ("database_id", "hpo_id")
KNOWN_COLUMNS = (
    "database_id",
    "disease_name",
    "qualifier",
    "hpo_id",
    "reference",
    "evidence",
    "onset",
    "frequency",
    "sex",
    "modifier",
    "aspect",
    "biocuration",
)


def parse_hpoa(path: Path, *, source: str = "hpo", role: str = "hpo_disease_annotations") -> ParseResult:
    version, release_date, schema_name, issues = peek_source_metadata(path, source, role)
    result = ParseResult(
        source=source,
        file_path=str(path),
        role=role,
        version=version,
        release_date=release_date,
        schema_name=schema_name or "hpoa_tsv",
        issues=list(issues),
    )
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
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

    header_index = _header_index(lines)
    if header_index is None:
        result.issues.append(
            Issue(
                code="schema_mismatch",
                message=f"{path.name} has no HPOA column header.",
                severity="error",
                source=source,
                file_path=str(path),
            )
        )
        return result

    columns = [item.strip().lower() for item in lines[header_index].split("\t")]
    result.detected_fields = columns
    missing = [name for name in REQUIRED_COLUMNS if name not in columns]
    if missing:
        result.issues.append(
            Issue(
                code="schema_mismatch",
                message=f"{path.name} is missing required HPOA columns: {', '.join(missing)}",
                severity="error",
                source=source,
                file_path=str(path),
            )
        )
        return result

    unknown = [name for name in columns if name and name not in KNOWN_COLUMNS]
    if unknown:
        result.issues.append(
            Issue(
                code="unexpected_hpoa_columns",
                message=f"{path.name} has extra columns that were preserved as provenance: {', '.join(unknown)}",
                severity="info",
                source=source,
                file_path=str(path),
            )
        )

    diseases: dict[str, Entity] = {}
    for line_no, raw in enumerate(lines[header_index + 1 :], start=header_index + 2):
        if not raw.strip() or raw.startswith("#"):
            continue
        values = raw.split("\t")
        row = {columns[index]: values[index].strip() if index < len(values) else "" for index in range(len(columns))}
        disease = parse_identifier(row.get("database_id", ""))
        phenotype = parse_identifier(row.get("hpo_id", ""))
        if disease is None or phenotype is None:
            result.issues.append(
                Issue(
                    code="unparsed_identifier",
                    message=f"Skipped HPOA row {line_no}: identifiers were not stable.",
                    severity="warning",
                    source=source,
                    file_path=str(path),
                    subject=row.get("database_id") or row.get("hpo_id"),
                )
            )
            continue
        if disease.curie not in diseases:
            diseases[disease.curie] = Entity(
                entity_type="disease",
                identifier=disease,
                label=row.get("disease_name") or None,
                labels_by_lang={"en": row["disease_name"]} if row.get("disease_name") else {},
                source=source,
                source_file=path.name,
                source_version=result.version,
                source_release_date=result.release_date,
                source_record_id=disease.curie,
                provenance={"from": "phenotype.hpoa"},
            )
        original, normalized = normalize_frequency(row.get("frequency") or None)
        polarity = polarity_from(qualifier=row.get("qualifier"), frequency_normalized=normalized)
        extras = {key: value for key, value in row.items() if key not in KNOWN_COLUMNS and value}
        result.relationships.append(
            Relationship(
                rel_type="has_phenotype",
                subject=disease,
                object=phenotype,
                polarity=polarity,
                frequency=original,
                frequency_normalized=normalized,
                evidence=row.get("evidence") or None,
                qualifier=row.get("qualifier") or None,
                onset=row.get("onset") or None,
                sex=row.get("sex") or None,
                aspect=row.get("aspect") or None,
                source=source,
                source_file=path.name,
                source_version=result.version,
                source_release_date=result.release_date,
                source_record_id=f"{disease.curie}|{phenotype.curie}|{line_no}",
                provenance={
                    "reference": row.get("reference") or None,
                    "modifier": row.get("modifier") or None,
                    "biocuration": row.get("biocuration") or None,
                    "extra_columns": extras or None,
                    "line": line_no,
                },
            )
        )
    result.entities.extend(diseases.values())
    return result


def _header_index(lines: list[str]) -> int | None:
    for index, line in enumerate(lines):
        if line.startswith("#"):
            continue
        lowered = line.lower()
        if "database_id" in lowered and "hpo_id" in lowered:
            return index
    return None
