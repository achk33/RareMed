"""Read-only discovery of manually provided source files.

File contents are not opened. A later importer can consume the same directory
layout without this module ever writing into data/raw.
"""

from dataclasses import dataclass
from pathlib import Path

from app.schemas.dataset import DiscoveredFile, DiscoveryReport, ReservedDirectory, SourceDiscovery

MAX_FILES_PER_SOURCE = 200
SKIP_NAMES = {"readme.md", ".gitkeep", "desktop.ini", "thumbs.db"}

DISCOVERY_NOTE = (
    "File listing records names and sizes only. Parsing is a separate ingestion "
    "step and never modifies files in data/raw."
)


@dataclass(frozen=True)
class SourceSpec:
    source: str
    relative_directory: str
    suffixes: tuple[str, ...]


SOURCE_SPECS = (
    SourceSpec("hpo", "raw/hpo", (".json", ".obo", ".owl", ".hpoa")),
    SourceSpec("orphadata", "raw/orphadata", (".xml", ".zip")),
    SourceSpec("mondo", "raw/mondo", (".json", ".owl", ".obo")),
    SourceSpec("literature", "raw/literature", (".pdf", ".txt", ".csv", ".md")),
)

RESERVED = (
    ("processed", "Normalized entities, relationships, mappings, and import manifests."),
    ("imports", "Import-ready graph node and edge records produced by ingestion."),
)


def discover_sources(root: Path) -> DiscoveryReport:
    root = root.resolve()
    if not root.exists() or not root.is_dir():
        return DiscoveryReport(
            readable=False,
            note=DISCOVERY_NOTE,
            sources=[],
            sample_files=[],
            reserved_directories=[],
        )

    sources = [_scan_source(root, spec) for spec in SOURCE_SPECS]
    samples_dir = root / "samples"
    sample_files = []
    if samples_dir.is_dir():
        sample_files = sorted(
            path.name
            for path in samples_dir.iterdir()
            if path.is_file() and path.suffix.lower() == ".json" and path.name.lower() not in SKIP_NAMES
        )

    reserved = [
        ReservedDirectory(name=name, present=(root / name).is_dir(), purpose=purpose)
        for name, purpose in RESERVED
    ]
    return DiscoveryReport(
        readable=True,
        note=DISCOVERY_NOTE,
        sources=sources,
        sample_files=sample_files,
        reserved_directories=reserved,
    )


def _scan_source(root: Path, spec: SourceSpec) -> SourceDiscovery:
    directory = root / spec.relative_directory
    if not directory.is_dir():
        return SourceDiscovery(
            source=spec.source,
            relative_directory=spec.relative_directory,
            present=False,
            file_count=0,
            truncated=False,
            files=[],
        )

    matches: list[Path] = []
    for path in directory.rglob("*"):
        if not path.is_file():
            continue
        if path.name.lower() in SKIP_NAMES:
            continue
        if path.suffix.lower() not in spec.suffixes:
            continue
        if not _stays_inside(root, path):
            continue
        matches.append(path)

    matches.sort(key=lambda item: item.relative_to(root).as_posix())
    truncated = len(matches) > MAX_FILES_PER_SOURCE
    visible = matches[:MAX_FILES_PER_SOURCE]
    files = [
        DiscoveredFile(
            name=path.name,
            relative_path=path.relative_to(root).as_posix(),
            size_bytes=path.stat().st_size,
            suffix=path.suffix.lower(),
        )
        for path in visible
    ]
    return SourceDiscovery(
        source=spec.source,
        relative_directory=spec.relative_directory,
        present=True,
        file_count=len(matches),
        truncated=truncated,
        files=files,
    )


def _stays_inside(root: Path, path: Path) -> bool:
    try:
        path.resolve().relative_to(root)
    except ValueError:
        return False
    return True
