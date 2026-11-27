from dataclasses import replace

from fastapi.testclient import TestClient
from opensearchpy import OpenSearch

from app.db.keyword_index import KeywordIndex
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


def test_health_reports_an_unreachable_keyword_index(settings, services):
    broken = KeywordIndex(
        OpenSearch(hosts=["http://127.0.0.1:1"], timeout=2, max_retries=0), "unreachable"
    )
    client = TestClient(create_app(settings, replace(services, keyword_index=broken)))
    response = client.get("/api/health")
    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}
