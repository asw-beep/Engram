from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://engram:engram@127.0.0.1:55432/engram"
    qdrant_url: str = "http://127.0.0.1:6333"
    qdrant_collection: str = "chunks_bge_m3_v1"
    storage_dir: str = "../data/files"

    embedding_model_id: str = "BAAI/bge-m3"
    embedding_model_revision: str = "5617a9f61b028005a4858fdac845db406aefb181"
    embedding_dimension: int = 1024
    embedding_device: str = "cuda"
    embedding_batch_size: int = 8

    openrouter_api_key: str = ""
    llm_model: str = "nvidia/nemotron-3.5-super-vl:free"
    llm_fallback_model: str = "google/gemma-4-31b-it:free"
    llm_timeout_seconds: float = 60.0
    retry_wait_seconds: float = 1.0

    # Calibrated with BGE-M3 on 10 smoke questions (docs/phase-1-smoke-results.md).
    evidence_min_score: float = 0.50
    max_chunk_tokens: int = 512
    chunk_overlap_tokens: int = 50
    retrieval_limit: int = 20
    max_passages: int = 8
    max_context_tokens: int = 4000
    max_question_chars: int = 2000
    max_upload_bytes: int = 25 * 1024 * 1024

    github_token: str | None = None
    # Repository tarballs are saved here while a sync reads them, inside the project's data/.
    download_dir: str = "../data/downloads"


@lru_cache
def get_settings() -> Settings:
    return Settings()
