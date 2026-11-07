"""The long-lived collaborators the app needs, built once from settings."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from qdrant_client import QdrantClient

from app.config import Settings
from app.db.base import build_session_factory
from app.db.models import IngestionJob, Source
from app.db.vector_index import VectorIndex
from app.embedding.bge_m3 import BgeM3Embedder
from app.generation.openrouter import OpenRouterProvider
from app.generation.resilient import ResilientLLM
from app.ingestion.connectors.base import Connector, ConnectorError
from app.ingestion.connectors.upload import UploadConnector
from app.ingestion.pipeline import IngestionDeps
from app.retrieval.dense import DenseRetriever
from app.storage.files import FileStore


@dataclass(frozen=True)
class Services(IngestionDeps):
    llm: Any = None
    retriever: Any = None


def build_services(settings: Settings) -> Services:
    file_store = FileStore(Path(settings.storage_dir))

    def connector_for(source: Source, job: IngestionJob) -> Connector:
        if source.type == "upload":
            return UploadConnector(file_store, job.input.get("uploads", []))
        raise ConnectorError(f"Unsupported source type {source.type}")

    embedder = BgeM3Embedder(settings)
    index = VectorIndex(
        QdrantClient(url=settings.qdrant_url, check_compatibility=False),
        settings.qdrant_collection,
        settings.embedding_dimension,
    )
    http = httpx.Client()

    def provider(model: str, structured: bool) -> OpenRouterProvider:
        return OpenRouterProvider(
            settings.openrouter_api_key,
            model,
            structured=structured,
            client=http,
            timeout=settings.llm_timeout_seconds,
        )

    return Services(
        session_factory=build_session_factory(settings.database_url),
        file_store=file_store,
        embedder=embedder,
        index=index,
        connector_for=connector_for,
        settings=settings,
        retriever=DenseRetriever(embedder, index),
        llm=ResilientLLM(
            primary=provider(settings.llm_model, structured=True),
            fallback=provider(settings.llm_fallback_model, structured=False),
        ),
    )
