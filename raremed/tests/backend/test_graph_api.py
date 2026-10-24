from pathlib import Path

from app.graph.jobs import load_graph, use_memory_store
from app.ingestion.pipeline import IngestionPipeline
from tests.backend.conftest import register_user, set_role

FIXTURES = Path(__file__).parent / "fixtures" / "ingestion" / "complete"


def test_graph_endpoints_search_and_retrieve(sqlite_bundle, tmp_path: Path, monkeypatch):
    from app.core.config import get_settings

    root = tmp_path / "data"
    import shutil

    shutil.copytree(FIXTURES, root, dirs_exist_ok=True)
    IngestionPipeline(root).run(run_id="api-src")
    store = use_memory_store(True)
    store.nodes.clear()
    store.edges.clear()
    store.evidence.clear()
    monkeypatch.setattr(get_settings(), "data_root", root)
    try:
        load_graph(root, store=store)
        client = sqlite_bundle["client"]
        register_user(client)
        set_role(sqlite_bundle["factory"], "person@example.com", "clinician")

        status = client.get("/api/v1/graph/status")
        assert status.status_code == 200
        assert status.json()["loaded"] is True
        assert status.json()["inferred_relationship_count"] == 0

        diseases = client.get("/api/v1/graph/diseases", params={"q": "Alexander"})
        assert diseases.status_code == 200
        assert any(item["curie"] == "ORPHA:58" for item in diseases.json())

        phenotypes = client.get("/api/v1/graph/phenotypes", params={"q": "Macrocephaly"})
        assert any(item["curie"] == "HP:0000256" for item in phenotypes.json())

        detail = client.get("/api/v1/graph/diseases/ORPHA:58")
        assert detail.status_code == 200
        body = detail.json()
        assert body["disease"]["label"] == "Alexander disease"
        assert any(item["end"] == "HP:0000256" and item["polarity"] == "present" for item in body["phenotypes"])
        assert any(item["polarity"] == "absent" for item in body["phenotypes"])

        evidence = client.get("/api/v1/graph/diseases/ORPHA:58/phenotypes", params={"polarity": "present"})
        assert evidence.status_code == 200
        assert all(item["polarity"] == "present" for item in evidence.json())

        neighborhood = client.get("/api/v1/graph/neighborhood", params={"curie": "ORPHA:58", "depth": 1, "limit": 20})
        assert neighborhood.status_code == 200
        assert neighborhood.json()["center"]["curie"] == "ORPHA:58"
        assert neighborhood.json()["bounded"] is True

        provenance = client.get("/api/v1/graph/provenance", params={"curie": "ORPHA:58"})
        assert provenance.status_code == 200
        assert provenance.json()
        assert all(item["inferred"] is False for item in provenance.json())
    finally:
        store.nodes.clear()
        store.edges.clear()
        store.evidence.clear()
        use_memory_store(False)
