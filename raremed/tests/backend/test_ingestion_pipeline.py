import json
from pathlib import Path

import pytest

from app.ingestion.errors import MissingRequiredSourcesError
from app.ingestion.pipeline import IngestionPipeline, rollback_current
from tests.backend.conftest import register_user, set_role

FIXTURES = Path(__file__).parent / "fixtures" / "ingestion" / "complete"


def test_pipeline_is_idempotent_and_exports_graph_records(tmp_path: Path):
    root = tmp_path / "data"
    _copy_fixtures(root)
    first = IngestionPipeline(root).run(run_id="run-a")
    second = IngestionPipeline(root).run(run_id="run-b")
    assert first["counts"]["entities"] == second["counts"]["entities"]
    assert first["counts"]["relationships"] == second["counts"]["relationships"]
    entities = _jsonl(root / "processed" / "runs" / "run-b" / "entities.jsonl")
    curies = [item["identifier"]["curie"] for item in entities]
    assert curies.count("ORPHA:58") == 1
    assert curies.count("HP:0000256") == 1
    assert curies.count("MONDO:0008762") == 1
    relationships = _jsonl(root / "processed" / "runs" / "run-b" / "relationships.jsonl")
    phenotypes = [
        item
        for item in relationships
        if item["rel_type"] == "has_phenotype" and item["subject"]["curie"] == "ORPHA:58"
    ]
    assert any(item["polarity"] == "present" and item["object"]["curie"] == "HP:0000256" for item in phenotypes)
    assert any(item["polarity"] == "absent" and item["object"]["curie"] == "HP:0001250" for item in phenotypes)
    mappings = _jsonl(root / "processed" / "runs" / "run-b" / "mappings.jsonl")
    mondo_maps = [
        item
        for item in mappings
        if item["subject"]["curie"] == "ORPHA:58" and item["object"]["namespace"] == "MONDO"
    ]
    assert len({item["object"]["curie"] for item in mondo_maps}) == 2
    warnings = _jsonl(root / "processed" / "runs" / "run-b" / "warnings.jsonl")
    assert any(item["code"] == "ambiguous_mapping" for item in warnings)
    nodes = _jsonl(root / "imports" / "runs" / "run-b" / "nodes.jsonl")
    edges = _jsonl(root / "imports" / "runs" / "run-b" / "edges.jsonl")
    assert nodes and edges
    current = json.loads((root / "processed" / "current.json").read_text(encoding="utf-8"))
    assert current["run_id"] == "run-b"
    rollback_current(root, "run-a")
    restored = json.loads((root / "processed" / "current.json").read_text(encoding="utf-8"))
    assert restored["run_id"] == "run-a"
    original = (FIXTURES / "raw" / "hpo" / "hp.json").read_text(encoding="utf-8")
    assert (root / "raw" / "hpo" / "hp.json").read_text(encoding="utf-8") == original


def test_strict_run_fails_when_required_sources_are_absent(tmp_path: Path):
    root = tmp_path / "empty"
    (root / "raw" / "hpo").mkdir(parents=True)
    with pytest.raises(MissingRequiredSourcesError) as caught:
        IngestionPipeline(root, strict=True).run()
    message = str(caught.value)
    assert "hp.obo" in message
    assert "phenotype.hpoa" in message


def test_non_strict_run_reports_missing_required_files(tmp_path: Path):
    root = tmp_path / "data"
    _copy_fixtures(root)
    (root / "raw" / "hpo" / "hp.obo").unlink()
    (root / "raw" / "hpo" / "phenotype.hpoa").unlink()
    payload = IngestionPipeline(root, strict=False).run(run_id="partial")
    assert "hpo/hp.obo" in payload["missing_required"]
    assert "hpo/phenotype.hpoa" in payload["missing_required"]
    assert payload["counts"]["entities"] > 0
    assert any(item["code"] == "required_source_missing" for item in payload["warnings"])


def test_ingestion_api_requires_staff_and_records_a_run(sqlite_bundle, tmp_path: Path, monkeypatch):
    root = tmp_path / "data"
    _copy_fixtures(root)
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "data_root", root)
    client = sqlite_bundle["client"]
    register_user(client)
    denied = client.get("/api/v1/ingestion/status")
    assert denied.status_code == 403
    set_role(sqlite_bundle["factory"], "person@example.com", "clinician")
    status = client.get("/api/v1/ingestion/status")
    assert status.status_code == 200
    body = status.json()
    assert "hp.obo" in " ".join(body["missing_required"]) or body["sources"]
    run = client.post("/api/v1/ingestion/run", json={"strict": False})
    assert run.status_code == 200
    imported = run.json()
    assert imported["current_run"] is not None
    assert imported["counts"]["entities"] > 0
    assert imported["last_successful_import"]


def _copy_fixtures(root: Path) -> None:
    import shutil

    shutil.copytree(FIXTURES, root, dirs_exist_ok=True)


def _jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
