import threading
from dataclasses import replace
from uuid import uuid4

from fastapi.testclient import TestClient
from opensearchpy import OpenSearch

from app.db.keyword_index import KeywordIndex
from app.main import create_app
from tests.fakes import FakeEmbedder, FakeReranker


class WatchedEmbedder(FakeEmbedder):
    """Records whether anything asked for a query vector, which loads the real model."""

    def __init__(self, error: Exception | None = None):
        self.loaded = threading.Event()
        self.error = error

    def embed_query(self, text: str) -> list[float]:
        self.loaded.set()
        if self.error is not None:
            raise self.error
        return super().embed_query(text)


def test_model_is_loaded_at_startup_when_asked(settings, services):
    embedder = WatchedEmbedder()
    app = create_app(
        settings.model_copy(update={"preload_embedding_model": True}),
        replace(services, embedder=embedder),
    )
    with TestClient(app):
        assert embedder.loaded.wait(timeout=5)


def test_model_waits_for_the_first_request_by_default(settings, services):
    embedder = WatchedEmbedder()
    with TestClient(create_app(settings, replace(services, embedder=embedder))):
        assert not embedder.loaded.wait(timeout=0.5)


def test_a_failed_model_load_at_startup_does_not_stop_the_app(settings, services):
    embedder = WatchedEmbedder(error=OSError("no model files"))
    app = create_app(
        settings.model_copy(update={"preload_embedding_model": True}),
        replace(services, embedder=embedder),
    )
    with TestClient(app) as client:
        assert embedder.loaded.wait(timeout=5)
        assert client.get("/api/health").status_code == 200


class WatchedReranker(FakeReranker):
    """Records whether anything asked for scores, which loads the real model."""

    def __init__(self):
        super().__init__()
        self.loaded = threading.Event()

    def score(self, query: str, passages: list[str]) -> list[float]:
        self.loaded.set()
        return super().score(query, passages)


def test_the_reranker_is_loaded_at_startup_too(settings, services):
    reranker = WatchedReranker()
    app = create_app(
        settings.model_copy(update={"preload_embedding_model": True}),
        replace(services, embedder=WatchedEmbedder(), reranker=reranker),
    )
    with TestClient(app):
        assert reranker.loaded.wait(timeout=5)


def test_a_failed_embedding_model_load_still_loads_the_reranker(settings, services):
    reranker = WatchedReranker()
    app = create_app(
        settings.model_copy(update={"preload_embedding_model": True}),
        replace(services, embedder=WatchedEmbedder(OSError("no model files")), reranker=reranker),
    )
    with TestClient(app):
        assert reranker.loaded.wait(timeout=5)


def test_startup_creates_a_missing_keyword_index(settings, services, opensearch_client):
    missing = KeywordIndex(opensearch_client, f"chunks_test_{uuid4().hex}")
    try:
        with TestClient(create_app(settings, replace(services, keyword_index=missing))):
            assert opensearch_client.indices.exists(index=missing.index)
    finally:
        opensearch_client.indices.delete(index=missing.index, ignore_unavailable=True)


def test_an_unreachable_keyword_index_does_not_stop_startup(settings, services):
    broken = KeywordIndex(
        OpenSearch(hosts=["http://127.0.0.1:1"], timeout=2, max_retries=0), "unreachable"
    )
    with TestClient(create_app(settings, replace(services, keyword_index=broken))) as client:
        assert client.get("/api/health").status_code == 503
