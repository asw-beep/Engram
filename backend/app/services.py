"""The long-lived collaborators the app needs, built once from settings."""

from collections.abc import Callable
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
from app.ingestion.connectors.github import GitHubConnector
from app.ingestion.connectors.upload import UploadConnector
from app.ingestion.pipeline import IngestionDeps
from app.retrieval.dense import DenseRetriever
from app.storage.files import FileStore


@dataclass(frozen=True)
class Services(IngestionDeps):
    llm: Any = None
    retriever: Any = None


def make_connector_for(
    file_store: FileStore, github_client: httpx.Client, settings: Settings
) -> Callable[[Source, IngestionJob], Connector]:
    def connector_for(source: Source, job: IngestionJob) -> Connector:
        if source.type == "upload":
            return UploadConnector(file_store, job.input.get("uploads", []))
        if source.type == "github":
            return GitHubConnector(
                source.config["repository"],
                source.config["branch"],
                source.config["include_paths"],
                settings.github_token,
                github_client,
                settings.max_upload_bytes,
                temp_dir=Path(settings.download_dir),
                retry_wait=settings.retry_wait_seconds,
            )
        raise ConnectorError(f"Unsupported source type {source.type}")

    return connector_for


def build_services(settings: Settings) -> Services:
    file_store = FileStore(Path(settings.storage_dir))
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
        connector_for=make_connector_for(file_store, httpx.Client(timeout=30.0), settings),
        settings=settings,
        retriever=DenseRetriever(embedder, index),
        llm=ResilientLLM(
            primary=provider(settings.llm_model, structured=True),
            fallback=provider(settings.llm_fallback_model, structured=False),
        ),
    )
