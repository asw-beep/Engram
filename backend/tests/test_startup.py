import threading
from dataclasses import replace

from fastapi.testclient import TestClient

from app.main import create_app
from tests.fakes import FakeEmbedder


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
