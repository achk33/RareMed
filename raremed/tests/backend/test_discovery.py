from pathlib import Path

from app.core.config import get_settings
from app.ingestion.discovery import discover_sources
from app.ingestion.samples import load_ui_fixtures


SENTINEL = "PHENOTYPE_CONTENT_SENTINEL_SHOULD_NOT_LEAK"


def _write(path: Path, content: str = SENTINEL) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_discovery_lists_names_and_does_not_read_contents(tmp_path: Path):
    _write(tmp_path / "raw" / "hpo" / "hp.json")
    _write(tmp_path / "raw" / "hpo" / "README.md", "notes")
    _write(tmp_path / "raw" / "mondo" / "mondo.json")
    _write(tmp_path / "raw" / "orphadata" / "nested" / "en_product1.xml")
    _write(tmp_path / "raw" / "literature" / "notes.md", "not clinical text")

    report = discover_sources(tmp_path)
    dumped = report.model_dump_json()

    assert SENTINEL not in dumped
    assert report.readable is True
    by_source = {source.source: source for source in report.sources}
    assert by_source["hpo"].file_count == 1
    assert by_source["hpo"].files[0].name == "hp.json"
    assert by_source["hpo"].files[0].relative_path == "raw/hpo/hp.json"
    assert by_source["mondo"].file_count == 1
    assert by_source["orphadata"].file_count == 1
    assert by_source["literature"].file_count == 1
    assert all(item.name != "README.md" for source in report.sources for item in source.files)


def test_missing_data_root_is_reported(tmp_path: Path):
    report = discover_sources(tmp_path / "absent")
    assert report.readable is False
    assert report.sources == []


def test_samples_ignore_unmarked_json_and_never_scan_raw(tmp_path: Path):
    _write(
        tmp_path / "samples" / "ui-demo-message.json",
        """
        {
          "kind": "ui-fixture",
          "synthetic": true,
          "id": "interface-check",
          "locale": "en",
          "text": "Synthetic interface check.",
          "notice": "Synthetic demonstration text."
        }
        """,
    )
    _write(tmp_path / "samples" / "not-a-fixture.json", '{"kind": "other", "synthetic": false}')
    _write(tmp_path / "raw" / "hpo" / "hp.json", '{"id": "HP:0000001"}')

    loaded = load_ui_fixtures(tmp_path)
    assert [item.id for item in loaded.fixtures] == ["interface-check"]
    assert "HP:0000001" not in loaded.model_dump_json()


def test_local_raw_files_are_listed_without_being_opened():
    root = get_settings().data_root
    hp = root / "raw" / "hpo" / "hp.json"
    if not hp.is_file():
        import pytest

        pytest.skip("No local HPO file in data/raw/hpo.")

    report = discover_sources(root)
    dumped = report.model_dump_json()
    names = [item.name for source in report.sources for item in source.files]
    assert "hp.json" in names
    assert "mondo.json" in names
    assert dumped.count("hp.json") >= 1
    assert "id" not in dumped or "HP:" not in dumped
