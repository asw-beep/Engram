"""run_ingestion: fetch, compare, parse, chunk and save each file of a job (spec section 5).

Embedding and publishing come later, so for now every processed file leaves its chunks
waiting and a job with any processed file ends `awaiting_embedding`.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any
from uuid import UUID, uuid4, uuid5

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings
from app.db.constants import OPEN_JOB_STATUSES, JobStatus
from app.db.models import Chunk, Document, DocumentVersion, IngestionJob, Source
from app.ingestion.chunking import chunk_document
from app.ingestion.connectors.base import Connector, ConnectorError
from app.ingestion.parsers import parse_file
from app.ingestion.types import FetchedFile, ParseError
from app.storage.files import FileStore, content_hash

logger = logging.getLogger(__name__)

PROCESSED, SKIPPED, FAILED = "processed", "skipped", "failed"


@dataclass(frozen=True)
class IngestionDeps:
    session_factory: sessionmaker[Session]
    file_store: FileStore
    embedder: Any  # the Embedder protocol; only count_tokens is used until publishing exists
    index: Any  # the vector index, used once publishing exists
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
    counts = _zero_counts()
    errors: list[dict[str, str]] = []
    connector = deps.connector_for(session.get(Source, job.source_id), job)
    try:
        items = list(connector.list_items())
        if not items:
            errors.append({"path": "", "reason": "no supported files found"})
            _finish(session, job, JobStatus.FAILED, counts, errors)
            return
        for item in items:
            fetched = connector.fetch(item)
            try:
                outcome = _ingest_file(session, job, fetched, deps)
            except ParseError as error:
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
    _finish(session, job, _final_status(counts), counts, errors)


def _ingest_file(
    session: Session, job: IngestionJob, fetched: FetchedFile, deps: IngestionDeps
) -> str:
    """Save one file's version and chunks, unless that content is already saved."""
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
            # Published already: skip. Saved but not published: resume at embedding.
            return SKIPPED if version_id == document.current_version_id else PROCESSED

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
    return PROCESSED


def _final_status(counts: dict[str, int]) -> JobStatus:
    if counts[PROCESSED]:
        return JobStatus.AWAITING_EMBEDDING
    if not counts[SKIPPED]:
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
