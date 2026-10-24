"""Inspect data/raw for expected medical sources without modifying them."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from xml.etree import ElementTree as ET

from app.ingestion.discovery import SKIP_NAMES
from app.ingestion.records import Issue

NAMED_REQUIRED = (
    ("hpo", "hp.obo", "hpo_ontology_obo"),
    ("hpo", "phenotype.hpoa", "hpo_disease_annotations"),
)

NAMED_OPTIONAL = (
    ("hpo", "hp.json", "hpo_ontology_json"),
    ("hpo", "hp.owl", "hpo_ontology_owl"),
    ("mondo", "mondo.json", "mondo_ontology_json"),
    ("mondo", "mondo.obo", "mondo_ontology_obo"),
    ("mondo", "mondo.owl", "mondo_ontology_owl"),
)

ORPHADATA_ROLES = (
    ("product1", "orphadata_diseases"),
    ("product3", "orphadata_classifications"),
    ("product4", "orphadata_hpo_associations"),
    ("product6", "orphadata_genes"),
    ("product7", "orphadata_disorder_associations"),
    ("product9", "orphadata_epidemiology"),
    ("funct_consequences", "orphadata_functional_consequences"),
)

SOURCE_DIRECTORIES = ("hpo", "orphadata", "mondo")
PARSEABLE_SUFFIXES = {".obo", ".json", ".owl", ".hpoa", ".xml"}
VERSION_IRI = re.compile(r"releases/(\d{4}-\d{2}-\d{2})", re.I)
JSON_VERSION_INFO = re.compile(r"versionInfo\"\s*,\s*\"val\"\s*:\s*\"([^\"]+)\"", re.I)
OBO_DATA_VERSION = re.compile(r"^data-version:\s*(.+)$", re.I | re.M)
OBO_DATE = re.compile(r"^date:\s*(.+)$", re.I | re.M)
HPOA_VERSION = re.compile(r"^#(?:version|date|dataset|hpo-version):\s*(.+)$", re.I | re.M)


@dataclass
class SourceFile:
    source: str
    role: str
    name: str
    path: Path
    relative_path: str
    size_bytes: int
    present: bool
    required: bool = False
    version: str | None = None
    release_date: str | None = None
    schema_name: str | None = None
    issues: list[Issue] = field(default_factory=list)


@dataclass
class Inventory:
    data_root: Path
    readable: bool
    files: list[SourceFile]
    issues: list[Issue]

    @property
    def missing_required(self) -> list[SourceFile]:
        return [item for item in self.files if item.required and not item.present]

    def files_for(self, source: str) -> list[SourceFile]:
        return [item for item in self.files if item.source == source]


def inspect_inventory(data_root: Path) -> Inventory:
    root = data_root.resolve()
    issues: list[Issue] = []
    files: list[SourceFile] = []
    if not root.is_dir():
        return Inventory(
            data_root=root,
            readable=False,
            files=[],
            issues=[
                Issue(
                    code="data_root_missing",
                    message=f"Data root is not a readable directory: {root}",
                    severity="error",
                )
            ],
        )

    seen: set[Path] = set()
    for source, name, role in NAMED_REQUIRED + NAMED_OPTIONAL:
        path = _find_named(root, source, name)
        required = (source, name) in {(item[0], item[1]) for item in NAMED_REQUIRED}
        record = _describe(root, source, role, name, path, required=required)
        files.append(record)
        if path is not None:
            seen.add(path.resolve())
        if required and path is None:
            issues.append(
                Issue(
                    code="required_source_missing",
                    message=f"Required source file is absent: {source}/{name}",
                    severity="error",
                    source=source,
                    file_path=f"raw/{source}/{name}",
                )
            )

    for path in _iter_raw_files(root / "raw" / "orphadata"):
        if path.resolve() in seen:
            continue
        role = _orphadata_role(path.name)
        if role is None:
            if path.suffix.lower() == ".xml":
                issues.append(
                    Issue(
                        code="unrecognized_orphadata_file",
                        message=f"Orphadata XML is present but not a known official product: {path.name}",
                        severity="info",
                        source="orphadata",
                        file_path=_relative(root, path),
                    )
                )
            continue
        files.append(_describe(root, "orphadata", role, path.name, path, required=False))
        seen.add(path.resolve())

    for source in SOURCE_DIRECTORIES:
        for path in _iter_raw_files(root / "raw" / source):
            if path.resolve() in seen:
                continue
            if path.suffix.lower() not in PARSEABLE_SUFFIXES:
                continue
            files.append(
                _describe(
                    root,
                    source,
                    f"{source}_other",
                    path.name,
                    path,
                    required=False,
                )
            )

    return Inventory(data_root=root, readable=True, files=files, issues=issues)


def _describe(
    root: Path,
    source: str,
    role: str,
    name: str,
    path: Path | None,
    *,
    required: bool,
) -> SourceFile:
    if path is None or not path.is_file():
        return SourceFile(
            source=source,
            role=role,
            name=name,
            path=root / "raw" / source / name,
            relative_path=f"raw/{source}/{name}",
            size_bytes=0,
            present=False,
            required=required,
            issues=[
                Issue(
                    code="required_source_missing" if required else "source_file_missing",
                    message=f"{'Required' if required else 'Expected'} source file is absent: {source}/{name}",
                    severity="error" if required else "info",
                    source=source,
                    file_path=f"raw/{source}/{name}",
                )
            ],
        )

    version, release_date, schema_name, peek_issues = peek_source_metadata(path, source, role)
    return SourceFile(
        source=source,
        role=role,
        name=path.name,
        path=path,
        relative_path=_relative(root, path),
        size_bytes=path.stat().st_size,
        present=True,
        required=required,
        version=version,
        release_date=release_date,
        schema_name=schema_name,
        issues=peek_issues,
    )


def peek_source_metadata(
    path: Path, source: str, role: str
) -> tuple[str | None, str | None, str | None, list[Issue]]:
    suffix = path.suffix.lower()
    issues: list[Issue] = []
    try:
        if suffix == ".xml":
            return _peek_xml(path, source, role)
        header = _read_header(path)
    except OSError as exc:
        issues.append(
            Issue(
                code="file_unreadable",
                message=f"Could not read {path.name}: {exc}",
                severity="error",
                source=source,
                file_path=str(path),
            )
        )
        return None, None, None, issues

    version = None
    release_date = None
    schema_name = None
    if suffix == ".json":
        schema_name = "obo_graphs_json"
        match = JSON_VERSION_INFO.search(header) or VERSION_IRI.search(header)
        if match:
            version = match.group(1)
            release_date = _as_date(version)
    elif suffix == ".obo":
        schema_name = "obo_text"
        data_version = OBO_DATA_VERSION.search(header)
        date_match = OBO_DATE.search(header)
        if data_version:
            version = data_version.group(1).strip()
            release_date = _as_date(version)
        if date_match:
            release_date = release_date or date_match.group(1).strip()
    elif suffix == ".hpoa":
        schema_name = "hpoa_tsv"
        versions = HPOA_VERSION.findall(header)
        if versions:
            version = versions[0].strip()
            release_date = _as_date(version)
    elif suffix == ".owl":
        schema_name = "owl_rdfxml" if "<rdf:RDF" in header or "<RDF" in header else "owl_other"
        match = VERSION_IRI.search(header) or JSON_VERSION_INFO.search(header)
        if match:
            version = match.group(1)
            release_date = _as_date(version)
    return version, release_date, schema_name, issues


def _peek_xml(path: Path, source: str, role: str) -> tuple[str | None, str | None, str | None, list[Issue]]:
    issues: list[Issue] = []
    try:
        for _event, element in ET.iterparse(path, events=("start",)):
            attribs = {key.split("}", 1)[-1]: value for key, value in element.attrib.items()}
            version = attribs.get("version") or attribs.get("Version")
            date = attribs.get("date") or attribs.get("Date")
            schema_name = _local(element.tag)
            return version, date, schema_name, issues
    except ET.ParseError as exc:
        issues.append(
            Issue(
                code="xml_unreadable",
                message=f"XML header could not be parsed in {path.name}: {exc}",
                severity="error",
                source=source,
                file_path=str(path),
            )
        )
    return None, None, None, issues


def _find_named(root: Path, source: str, name: str) -> Path | None:
    directory = root / "raw" / source
    if not directory.is_dir():
        return None
    target = name.lower()
    for path in _iter_raw_files(directory):
        if path.name.lower() == target:
            return path
    return None


def _orphadata_role(name: str) -> str | None:
    lowered = name.lower()
    for token, role in ORPHADATA_ROLES:
        if token in lowered:
            return role
    return None


def _iter_raw_files(directory: Path) -> list[Path]:
    if not directory.is_dir():
        return []
    matches: list[Path] = []
    for path in directory.rglob("*"):
        if not path.is_file():
            continue
        if path.name.lower() in SKIP_NAMES:
            continue
        matches.append(path)
    matches.sort(key=lambda item: item.as_posix().lower())
    return matches


def _read_header(path: Path, nbytes: int = 262144) -> str:
    with path.open("rb") as handle:
        return handle.read(nbytes).decode("utf-8", "replace")


def _relative(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _as_date(value: str | None) -> str | None:
    if not value:
        return None
    match = re.search(r"(\d{4}-\d{2}-\d{2})", value)
    return match.group(1) if match else None
