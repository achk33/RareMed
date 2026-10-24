def test_health_is_liveness_only(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "raremed-ai",
        "version": "0.6.0",
        "role": "decision-support",
    }
    assert response.headers["X-Request-ID"]
    assert response.headers["X-RareMed-Role"] == "decision-support"


def test_versioned_health_matches_root_probe(client):
    assert client.get("/api/v1/health").json() == client.get("/health").json()


def test_root_points_at_the_foundation_endpoints(client):
    body = client.get("/").json()
    assert body["health"] == "/health"
    assert body["status"] == "/api/v1/status"
    assert body["role"] == "decision-support"


def test_cors_allows_the_local_frontend(client):
    response = client.get("/health", headers={"Origin": "http://localhost:3000"})
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_cors_does_not_reflect_an_unknown_origin(client):
    response = client.get("/health", headers={"Origin": "https://example.invalid"})
    assert "access-control-allow-origin" not in response.headers
