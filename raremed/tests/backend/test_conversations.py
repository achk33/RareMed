import uuid

from tests.backend.conftest import register_user


def test_unknown_route_uses_the_error_envelope(client):
    response = client.get("/api/v1/missing")
    assert response.status_code == 404
    body = response.json()["error"]
    assert body["code"] == "not_found"
    assert body["request_id"]


def test_conversations_require_a_session(sqlite_client):
    response = sqlite_client.get("/api/v1/conversations")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthenticated"


def test_validation_error_hides_the_submitted_text(auth_client):
    created = auth_client.post("/api/v1/conversations", json={"locale": "en"})
    conversation_id = created.json()["id"]
    response = auth_client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"content": "   ", "locale": "en"},
    )
    assert response.status_code == 422
    dumped = response.text
    assert "validation_error" in dumped
    assert "input" not in response.json()["error"]


def test_conversation_workspace_round_trip(auth_client):
    created = auth_client.post("/api/v1/conversations", json={"locale": "fr"})
    assert created.status_code == 201
    conversation_id = created.json()["id"]
    assert created.json()["title"] == "New conversation"

    exchange = auth_client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"content": "  Synthetic interface check.  ", "locale": "fr"},
    )
    assert exchange.status_code == 201
    body = exchange.json()
    assert body["user_message"]["content"] == "Synthetic interface check."
    assert "validé cliniquement" in body["assistant_message"]["content"]
    assert body["assistant_message"]["role"] == "assistant"
    assert body["assistant_message"]["extra"]["hpo_entities"] == []
    assert body["assistant_message"]["extra"]["medical_evidence"] == []
    assert body["assistant_message"]["extra"]["diagnostic_session_id"] is None

    listing = auth_client.get("/api/v1/conversations")
    assert listing.status_code == 200
    assert listing.json()["items"][0]["title"] == "Synthetic interface check."
    assert listing.json()["items"][0]["message_count"] == 2
    assert listing.json()["total"] == 1

    detail = auth_client.get(f"/api/v1/conversations/{conversation_id}")
    assert len(detail.json()["messages"]) == 2

    missing = auth_client.get(f"/api/v1/conversations/{uuid.uuid4()}")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "conversation_not_found"

    renamed = auth_client.patch(
        f"/api/v1/conversations/{conversation_id}",
        json={"title": "Clinic note"},
    )
    assert renamed.json()["title"] == "Clinic note"
    assert renamed.json()["title_source"] == "manual"

    archived = auth_client.patch(
        f"/api/v1/conversations/{conversation_id}",
        json={"archived": True},
    )
    assert archived.json()["archived"] is True
    assert auth_client.get("/api/v1/conversations").json()["items"] == []
    hidden = auth_client.get("/api/v1/conversations?archived_only=true")
    assert hidden.json()["items"][0]["id"] == conversation_id

    search = auth_client.get("/api/v1/conversations?q=Clinic&include_archived=true")
    assert search.json()["items"][0]["id"] == conversation_id

    deleted = auth_client.delete(f"/api/v1/conversations/{conversation_id}")
    assert deleted.status_code == 204
    assert auth_client.get("/api/v1/conversations?include_archived=true").json()["items"] == []


def test_users_cannot_read_each_others_conversations(sqlite_client):
    register_user(sqlite_client, email="owner@example.com")
    created = sqlite_client.post("/api/v1/conversations", json={"locale": "en"})
    conversation_id = created.json()["id"]
    sqlite_client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"content": "Private note", "locale": "en"},
    )

    sqlite_client.cookies.clear()
    register_user(sqlite_client, email="other@example.com")
    listing = sqlite_client.get("/api/v1/conversations")
    assert listing.json()["items"] == []
    hidden = sqlite_client.get(f"/api/v1/conversations/{conversation_id}")
    assert hidden.status_code == 404
    assert hidden.json()["error"]["code"] == "conversation_not_found"
    assert "Private note" not in hidden.text
    deleted = sqlite_client.delete(f"/api/v1/conversations/{conversation_id}")
    assert deleted.status_code == 404


def test_invalid_uuid_is_rejected(auth_client):
    response = auth_client.get("/api/v1/conversations/not-a-uuid")
    assert response.status_code == 422
