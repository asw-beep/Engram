import logging
import threading
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import health, jobs, questions, sources
from app.config import Settings, get_settings
from app.embedding.base import Embedder
from app.ingestion.jobs import mark_interrupted_jobs
from app.services import Services, build_services

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None, services: Services | None = None) -> FastAPI:
    settings = settings or get_settings()
    services = services or build_services(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # One worker runs every job, so anything still queued or running was cut off.
        with services.session_factory() as session:
            interrupted = mark_interrupted_jobs(session)
        if interrupted:
            logger.warning("Marked %d unfinished ingestion jobs as interrupted", interrupted)
        try:
            services.index.ensure_collection()
        except Exception:
            # Keep starting, so /api/health can report that Qdrant is unavailable.
            logger.warning("Could not prepare the Qdrant collection at startup", exc_info=True)
        if settings.preload_embedding_model:
            threading.Thread(
                target=_load_model, args=(services.embedder,), name="model-load", daemon=True
            ).start()
        yield

    app = FastAPI(title="Engram", lifespan=lifespan)
    app.state.settings = settings
    app.state.services = services
    app.include_router(health.router)
    app.include_router(sources.router)
    app.include_router(jobs.router)
    app.include_router(questions.router)
    return app


def _load_model(embedder: Embedder) -> None:
    """Embed one query, which loads the model. A failure leaves the first request to retry."""
    started = time.monotonic()
    try:
        embedder.embed_query("load")
    except Exception:
        logger.warning("Could not load the embedding model at startup", exc_info=True)
        return
    logger.info("Embedding model loaded in %.1f s", time.monotonic() - started)
