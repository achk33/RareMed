from pathlib import Path

from app.graph.jobs import load_graph, use_memory_store
from app.ingestion.pipeline import IngestionPipeline
from tests.backend.conftest import register_user, set_role

FIXTURES = Path(__file__).parent / "fixtures" / "ingestion" / "complete"


def _load_memory_graph(tmp_path: Path, monkeypatch):
    from app.core.config import get_settings

    root = tmp_path / "data"
    import shutil

    shutil.copytree(FIXTURES, root, dirs_exist_ok=True)
    IngestionPipeline(root).run(run_id="explore-src")
    store = use_memory_store(True)
    store.nodes.clear()
    store.edges.clear()
    store.evidence.clear()
    monkeypatch.setattr(get_settings(), "data_root", root)
    load_graph(root, store=store)
    return store


def test_explore_search_expand_path_and_provenance(sqlite_bundle, tmp_path: Path, monkeypatch):
    store = _load_memory_graph(tmp_path, monkeypatch)
    client = sqlite_bundle["client"]
    register_user(client)
    set_role(sqlite_bundle["factory"], "person@example.com", "clinician")
    try:
        search = client.get(
            "/api/v1/graph/explore/search",
            params={"q": "Alexander", "kinds": "Disease", "limit": 12},
        )
        assert search.status_code == 200
        body = search.json()
        assert body["has_more"] is False
        assert any(item["curie"] == "ORPHA:58" for item in body["items"])

        neighborhood = client.get(
            "/api/v1/graph/explore/neighborhood",
            params={"curie": "ORPHA:58", "depth": 1, "limit": 40, "kinds": "Disease,Phenotype,Gene,InheritancePattern"},
        )
        assert neighborhood.status_code == 200
        found = neighborhood.json()
        assert found["center"]["curie"] == "ORPHA:58"
        assert found["bounded"] is True
        assert found["read_only"] is True
        assert found["edges"]
        assert all(item["inferred"] is False for item in found["edges"])

        expand = client.get("/api/v1/graph/explore/expand", params={"curie": "ORPHA:58", "limit": 8})
        assert expand.status_code == 200
        assert expand.json()["read_only"] is True
        assert expand.json()["edges"]

        path = client.get("/api/v1/graph/explore/path", params={"start": "ORPHA:58", "end": "HP:0000256"})
        assert path.status_code == 200
        assert any(item["curie"] == "ORPHA:58" for item in path.json()["nodes"])
        assert any(item["curie"] == "HP:0000256" for item in path.json()["nodes"])

        sources = client.get("/api/v1/graph/explore/sources")
        assert sources.status_code == 200
        assert sources.json()

        entity = client.get("/api/v1/graph/entities/ORPHA:58")
        assert entity.status_code == 200
        assert entity.json()["entity"]["curie"] == "ORPHA:58"
        assert entity.json()["evidence"]
        assert all(item["inferred"] is False for item in entity.json()["evidence"])
        assert all(item.get("source") for item in entity.json()["evidence"])
    finally:
        store.nodes.clear()
        store.edges.clear()
        store.evidence.clear()
        use_memory_store(False)


def test_explore_truncates_large_neighborhoods(sqlite_bundle, tmp_path: Path, monkeypatch):
    store = _load_memory_graph(tmp_path, monkeypatch)
    client = sqlite_bundle["client"]
    register_user(client)
    set_role(sqlite_bundle["factory"], "person@example.com", "clinician")
    try:
        tiny = client.get(
            "/api/v1/graph/explore/neighborhood",
            params={"curie": "ORPHA:58", "depth": 1, "limit": 1},
        )
        assert tiny.status_code == 200
        body = tiny.json()
        assert body["truncated"] is True
        assert len(body["edges"]) <= 1

        expand = client.get("/api/v1/graph/explore/expand", params={"curie": "ORPHA:58", "limit": 1})
        assert expand.status_code == 200
        assert expand.json()["truncated"] is True
        assert len(expand.json()["edges"]) <= 1
    finally:
        store.nodes.clear()
        store.edges.clear()
        store.evidence.clear()
        use_memory_store(False)


def test_explore_and_management_authorization(sqlite_bundle, tmp_path: Path, monkeypatch):
    store = _load_memory_graph(tmp_path, monkeypatch)
    client = sqlite_bundle["client"]
    try:
        anonymous = client.get("/api/v1/graph/explore/search", params={"q": "Alexander"})
        assert anonymous.status_code == 401

        register_user(client)
        user_forbidden = client.get("/api/v1/graph/explore/search", params={"q": "Alexander"})
        assert user_forbidden.status_code == 403
        user_load = client.post("/api/v1/graph/load", json={})
        assert user_load.status_code == 403

        clinical = client.get("/api/v1/graph/diseases", params={"q": "Alexander"})
        assert clinical.status_code == 200

        set_role(sqlite_bundle["factory"], "person@example.com", "clinician")
        staff_ok = client.get("/api/v1/graph/explore/search", params={"q": "Alexander"})
        assert staff_ok.status_code == 200
        staff_load = client.post("/api/v1/graph/load", json={})
        assert staff_load.status_code == 403

        set_role(sqlite_bundle["factory"], "person@example.com", "admin")
        admin_status = client.get("/api/v1/graph/status")
        assert admin_status.status_code == 200
    finally:
        store.nodes.clear()
        store.edges.clear()
        store.evidence.clear()
        use_memory_store(False)
