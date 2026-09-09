"""Phase 1 smoke tests: the app boots, /health responds, CORS is configured."""


def test_health_returns_ok(client):
    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["database"] == "connected"
    assert payload["version"]
    assert payload["timestamp"]


def test_root_describes_service(client):
    response = client.get("/")

    assert response.status_code == 200
    assert response.json()["health"] == "/health"


def test_cors_allows_local_frontend_origin(client):
    response = client.get("/health", headers={"Origin": "http://localhost:5173"})

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
