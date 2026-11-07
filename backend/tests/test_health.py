from fastapi.testclient import TestClient

from app.main import create_app


def test_health_ok(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_reports_unavailable_store(settings):
    broken = settings.model_copy(update={"qdrant_url": "http://localhost:1"})
    response = TestClient(create_app(broken)).get("/api/health")
    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}
