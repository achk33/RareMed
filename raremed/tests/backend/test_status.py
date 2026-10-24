from app.schemas.common import DependencyStatus
from app.schemas.status import OllamaStatus
from app.services.assistant import foundation_reply


def test_status_stays_available_when_dependencies_are_down(client, monkeypatch, tmp_path):
    monkeypatch.setattr(
        "app.services.status._probe_database",
        lambda: DependencyStatus(status="unavailable", detail="OperationalError"),
    )
    monkeypatch.setattr(
        "app.services.status.probe_neo4j",
        lambda: DependencyStatus(status="unavailable", detail="ServiceUnavailable"),
    )
    monkeypatch.setattr(
        "app.services.status._probe_ollama",
        lambda: OllamaStatus(
            status="unavailable",
            base_url="http://127.0.0.1:11434",
            detail="ConnectError",
        ),
    )
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "data_root", tmp_path)

    response = client.get("/api/v1/status")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "raremed-ai"
    assert body["version"] == "0.6.0"
    assert body["api_version"] == "v1"
    assert body["clinical_reasoning_enabled"] is False
    assert "not a clinically validated diagnostic tool" in body["decision_support_notice"]
    assert body["database"]["status"] == "unavailable"
    assert body["neo4j"]["status"] == "unavailable"
    assert body["ollama"]["status"] == "unavailable"
    assert body["datasets"]["total_files"] == 0


def test_graph_status_reports_that_nothing_is_loaded(sqlite_bundle, monkeypatch):
    from tests.backend.conftest import register_user, set_role

    monkeypatch.setattr(
        "app.services.status.probe_neo4j",
        lambda: DependencyStatus(status="unavailable", detail="ServiceUnavailable"),
    )
    client = sqlite_bundle["client"]
    register_user(client, email="clinician@example.com")
    set_role(sqlite_bundle["factory"], "clinician@example.com", "clinician")
    response = client.get("/api/v1/graph/status")
    assert response.status_code == 200
    body = response.json()
    assert body["loaded"] is False
    assert body["connection"]["status"] == "unavailable"
    assert "not invented" in body["note"]


def test_foundation_replies_refuse_clinical_reasoning():
    assert "not a clinically validated diagnostic tool" in foundation_reply("en")
    assert "validé cliniquement" in foundation_reply("fr")
    assert "ليست أداة تشخيص معتمدة سريريًا" in foundation_reply("ar")
    assert "suggest diseases" not in foundation_reply("en").split("does not")[0]
