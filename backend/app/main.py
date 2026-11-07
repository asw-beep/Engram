from fastapi import FastAPI
from qdrant_client import QdrantClient
from sqlalchemy import create_engine

from app.api import health
from app.config import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(title="Engram")
    app.state.settings = settings
    app.state.engine = create_engine(settings.database_url, pool_pre_ping=True)
    app.state.qdrant = QdrantClient(url=settings.qdrant_url, check_compatibility=False)
    app.include_router(health.router)
    return app
