"""The long-lived collaborators the app needs, built once from settings."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.config import Settings
from app.db.base import build_session_factory
from app.db.models import IngestionJob, Source
from app.ingestion.connectors.base import Connector, ConnectorError
from app.ingestion.connectors.upload import UploadConnector
from app.ingestion.pipeline import IngestionDeps
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

    return Services(
        session_factory=build_session_factory(settings.database_url),
        file_store=file_store,
        embedder=None,
        index=None,
        connector_for=connector_for,
        settings=settings,
    )
