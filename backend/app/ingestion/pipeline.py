"""run_ingestion: the per-file steps of spec section 5, from fetching to publishing.

Saving a file's version and chunks commits first. Embedding and publishing come after, so a
failure there leaves the old version searchable and a retry resumes at embedding.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import PurePosixPath
from uuid import UUID, uuid4, uuid5

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings
from app.db.constants import OPEN_JOB_STATUSES, JobStatus
from app.db.models import Chunk, Document, DocumentVersion, IngestionJob, Source
from app.db.vector_index import IndexedPoint, VectorIndex, is_transient_qdrant_error
from app.embedding.base import Embedder, EmbeddingOutOfMemory, embedding_text
from app.embedding.batching import embed_in_batches
from app.ingestion.chunking import chunk_document
from app.ingestion.connectors.base import Connector, ConnectorError, FileTooLarge
from app.ingestion.parsers import parse_file
from app.ingestion.types import FetchedFile, ParseError
from app.retrying import retry_transient
from app.storage.files import FileStore, content_hash

logger = logging.getLogger(__name__)

PROCESSED, SKIPPED, FAILED = "processed", "skipped", "failed"


class PublishError(Exception):
    """Embedding or publishing one file failed. The message is shown to the user."""


@dataclass(frozen=True)
class IngestionDeps:
    session_factory: sessionmaker[Session]
    file_store: FileStore
    embedder: Embedder
    index: VectorIndex
    connector_for: Callable[[Source, IngestionJob], Connector]
    settings: Settings


def run_ingestion(job_id: UUID, deps: IngestionDeps) -> None:
    with deps.session_factory() as session:
        job = _claim(session, job_id)
        if job is None:
            return
        try:
            _run(session, job, deps)
        except Exception:
            logger.exception("Ingestion job %s failed unexpectedly", job_id)
            session.rollback()
            errors = [*job.errors, {"path": "", "reason": "internal error"}]
            _finish(session, job, JobStatus.FAILED, job.file_counts, errors)


def publish_version(
    session: Session,
    version: DocumentVersion,
    vectors: dict[UUID, list[float]],
    index: VectorIndex,
    model_id: str,
    retry_wait: float = 1.0,
) -> None:
    """Spec step 7: add the version's points, make it current, then drop the old points."""
    document = session.get(Document, version.document_id)
    chunk_ids = session.scalars(
        select(Chunk.id).where(Chunk.document_version_id == version.id).order_by(Chunk.position)
    ).all()
    points = [
        IndexedPoint(
            chunk_id=chunk_id,
            vector=vectors[chunk_id],
            tenant_id=version.tenant_id,
            document_id=document.id,
            document_version_id=version.id,
            allowed_principals=list(document.allowed_principals),
        )
        for chunk_id in chunk_ids
    ]
    retry_transient(lambda: index.upsert(points), is_transient_qdrant_error, wait_base=retry_wait)

    old_version_id = document.current_version_id
    document.current_version_id = version.id
    session.execute(
        update(Chunk)
        .where(Chunk.document_version_id == version.id)
        .values(embedding_model=model_id, embedded_at=func.now())
    )
    session.commit()

    if old_version_id is not None and old_version_id != version.id:
        try:
            retry_transient(
                lambda: index.delete_version(old_version_id),
                is_transient_qdrant_error,
                wait_base=retry_wait,
            )
        except Exception:
            # Search rechecks the current version, so stale points are never shown.
            logger.warning(
                "Could not remove points of old version %s", old_version_id, exc_info=True
            )


def _claim(session: Session, job_id: UUID) -> IngestionJob | None:
    """Move a pending job to running, so the same job never runs twice."""
    result = session.execute(
        update(IngestionJob)
        .where(IngestionJob.id == job_id, IngestionJob.status == JobStatus.PENDING)
        .values(
            status=JobStatus.RUNNING,
            started_at=func.now(),
            finished_at=None,
            file_counts=_zero_counts(),
            errors=[],
        )
    )
    session.commit()
    return session.get(IngestionJob, job_id) if result.rowcount else None


def _run(session: Session, job: IngestionJob, deps: IngestionDeps) -> None:
    defer_embedding = bool(job.input.get("defer_embedding", False))
    counts = _zero_counts()
    errors: list[dict[str, str]] = []
    waiting = False
    connector = deps.connector_for(session.get(Source, job.source_id), job)
    try:
        items = list(connector.list_items())
        if not items:
            errors.append({"path": "", "reason": "no supported files found"})
            _finish(session, job, JobStatus.FAILED, counts, errors)
            return
        for item in items:
            try:
                fetched = connector.fetch(item)
                outcome, version_id = _save_file(session, job, fetched, deps)
                session.commit()
                if version_id is not None and defer_embedding:
                    _mark_waiting(session, version_id, job.id)
                    waiting = True
                elif version_id is not None:
                    _embed_and_publish(session, version_id, deps)
            except (ParseError, PublishError, FileTooLarge) as error:
                session.rollback()
                outcome = FAILED
                errors.append({"path": item.path, "reason": str(error)})
            counts[outcome] += 1
            job.file_counts = dict(counts)
            job.errors = list(errors)
            session.commit()
    except ConnectorError as error:
        session.rollback()
        errors.append({"path": "", "reason": str(error)})
        _finish(session, job, JobStatus.FAILED, counts, errors)
        return
    finally:
        connector.close()
    _finish(session, job, _final_status(counts, waiting), counts, errors)


def _save_file(
    session: Session, job: IngestionJob, fetched: FetchedFile, deps: IngestionDeps
) -> tuple[str, UUID | None]:
    """Spec steps 2 to 5. Returns the outcome and the version still to publish, if any."""
    item = fetched.item
    digest = content_hash(fetched.content)
    document = session.scalars(
        select(Document).where(
            Document.tenant_id == job.tenant_id,
            Document.source_id == job.source_id,
            Document.path == item.path,
        )
    ).one_or_none()
    if document is not None:
        version_id = session.scalars(
            select(DocumentVersion.id).where(
                DocumentVersion.tenant_id == job.tenant_id,
                DocumentVersion.document_id == document.id,
                DocumentVersion.content_hash == digest,
            )
        ).one_or_none()
        if version_id is not None:
            if version_id == document.current_version_id:
                return SKIPPED, None
            # Saved before but not current, such as a revert or an unfinished job.
            return PROCESSED, version_id

    storage_key = item.storage_key or deps.file_store.put(job.tenant_id, fetched.content)
    drafts = chunk_document(
        parse_file(item.path, fetched.content),
        deps.embedder.count_tokens,
        deps.settings.max_chunk_tokens,
        deps.settings.chunk_overlap_tokens,
    )
    if document is None:
        document = Document(
            id=uuid4(),
            tenant_id=job.tenant_id,
            source_id=job.source_id,
            path=item.path,
            file_type=PurePosixPath(item.path).suffix.lower().lstrip("."),
        )
        session.add(document)
        session.flush()
    version = DocumentVersion(
        id=uuid4(),
        tenant_id=job.tenant_id,
        document_id=document.id,
        content_hash=digest,
        revision=item.revision,
        storage_key=storage_key,
    )
    session.add(version)
    session.flush()
    session.add_all(
        Chunk(
            id=uuid5(version.id, str(draft.position)),
            tenant_id=job.tenant_id,
            document_version_id=version.id,
            position=draft.position,
            content=draft.content,
            heading_path=list(draft.heading_path),
            start_line=draft.start_line,
            end_line=draft.end_line,
            page_start=draft.page_start,
            page_end=draft.page_end,
            token_count=draft.token_count,
        )
        for draft in drafts
    )
    return PROCESSED, version.id


def _embed_and_publish(session: Session, version_id: UUID, deps: IngestionDeps) -> None:
    """Spec steps 6 and 7. Every chunk is embedded, because old points may be gone."""
    version = session.get(DocumentVersion, version_id)
    chunks = session.scalars(
        select(Chunk).where(Chunk.document_version_id == version_id).order_by(Chunk.position)
    ).all()
    texts = [embedding_text(tuple(chunk.heading_path), chunk.content) for chunk in chunks]
    try:
        vectors = embed_in_batches(deps.embedder, texts, deps.settings.embedding_batch_size)
    except EmbeddingOutOfMemory as error:
        raise PublishError("ran out of memory while embedding, even one chunk at a time") from error
    try:
        publish_version(
            session,
            version,
            {chunk.id: vector for chunk, vector in zip(chunks, vectors, strict=True)},
            deps.index,
            deps.embedder.model_id,
            retry_wait=deps.settings.retry_wait_seconds,
        )
    except Exception as error:
        logger.warning("Publishing version %s failed", version_id, exc_info=True)
        raise PublishError("could not save vectors to Qdrant") from error


def _mark_waiting(session: Session, version_id: UUID, job_id: UUID) -> None:
    """A deferred version waits for this job's import, and all its chunks for export,
    including ones embedded before."""
    session.execute(
        update(DocumentVersion)
        .where(DocumentVersion.id == version_id)
        .values(awaiting_job_id=job_id)
    )
    session.execute(
        update(Chunk)
        .where(Chunk.document_version_id == version_id, Chunk.embedded_at.is_not(None))
        .values(embedded_at=None)
    )
    session.commit()


def _final_status(counts: dict[str, int], waiting: bool) -> JobStatus:
    if waiting:
        return JobStatus.AWAITING_EMBEDDING
    if not counts[PROCESSED] and not counts[SKIPPED]:
        return JobStatus.FAILED
    return JobStatus.PARTIAL if counts[FAILED] else JobStatus.SUCCEEDED


def _finish(
    session: Session,
    job: IngestionJob,
    status: JobStatus,
    counts: dict[str, int],
    errors: list[dict[str, str]],
) -> None:
    job.status = status
    job.file_counts = dict(counts)
    job.errors = list(errors)
    if status not in OPEN_JOB_STATUSES:
        job.finished_at = func.now()
    session.commit()


def _zero_counts() -> dict[str, int]:
    return {PROCESSED: 0, SKIPPED: 0, FAILED: 0}
