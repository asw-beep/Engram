from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.constants import OPEN_JOB_STATUSES, JobStatus
from app.db.models import IngestionJob, Source
from app.storage.files import FileStore

RETRYABLE_STATUSES = (JobStatus.PARTIAL, JobStatus.FAILED, JobStatus.INTERRUPTED)


class JobAlreadyOpen(Exception):
    def __init__(self, job_id: UUID):
        super().__init__(f"job {job_id} is still open for this source")
        self.job_id = job_id


class JobNotRetryable(Exception):
    def __init__(self, status: str):
        super().__init__(f"A {status} job can't be retried")
        self.status = status


def create_job(session: Session, source: Source, input: dict) -> IngestionJob:
    """Add a pending job, unless the source already has an open one."""
    open_job_id = _open_job_id(session, source.tenant_id, source.id)
    if open_job_id is not None:
        raise JobAlreadyOpen(open_job_id)
    job = IngestionJob(
        tenant_id=source.tenant_id, source_id=source.id, status=JobStatus.PENDING, input=input
    )
    session.add(job)
    _commit_unless_another_job_opened(session, source.tenant_id, source.id)
    return job


def create_upload_job(
    session: Session,
    file_store: FileStore,
    source: Source,
    files: list[tuple[str, bytes]],
    defer_embedding: bool,
) -> IngestionJob:
    """Save the uploaded files first, so the job can be retried from storage."""
    uploads = [
        {"path": path, "storage_key": file_store.put(source.tenant_id, content)}
        for path, content in files
    ]
    return create_job(session, source, {"uploads": uploads, "defer_embedding": defer_embedding})


def retry_job(session: Session, job: IngestionJob) -> IngestionJob:
    """Put a job that ended badly back to pending, keeping its input."""
    if job.status not in RETRYABLE_STATUSES:
        raise JobNotRetryable(job.status)
    open_job_id = _open_job_id(session, job.tenant_id, job.source_id)
    if open_job_id is not None:
        raise JobAlreadyOpen(open_job_id)
    job.status = JobStatus.PENDING
    job.errors = []
    job.finished_at = None
    _commit_unless_another_job_opened(session, job.tenant_id, job.source_id)
    return job


def mark_interrupted_jobs(session: Session) -> int:
    """At startup, no job can still be queued or running, so mark those interrupted."""
    result = session.execute(
        update(IngestionJob)
        .where(IngestionJob.status.in_((JobStatus.PENDING, JobStatus.RUNNING)))
        .values(status=JobStatus.INTERRUPTED, finished_at=func.now())
    )
    session.commit()
    return result.rowcount


def get_source(session: Session, tenant_id: UUID, source_id: UUID) -> Source | None:
    return session.scalars(
        select(Source).where(Source.tenant_id == tenant_id, Source.id == source_id)
    ).one_or_none()


def list_sources(session: Session, tenant_id: UUID) -> list[Source]:
    return list(
        session.scalars(
            select(Source).where(Source.tenant_id == tenant_id).order_by(Source.type, Source.name)
        )
    )


def get_job(session: Session, tenant_id: UUID, job_id: UUID) -> IngestionJob | None:
    return session.scalars(
        select(IngestionJob).where(IngestionJob.tenant_id == tenant_id, IngestionJob.id == job_id)
    ).one_or_none()


def list_jobs(session: Session, tenant_id: UUID, limit: int = 50) -> list[IngestionJob]:
    return list(
        session.scalars(
            select(IngestionJob)
            .where(IngestionJob.tenant_id == tenant_id)
            .order_by(IngestionJob.created_at.desc(), IngestionJob.id)
            .limit(limit)
        )
    )


def _commit_unless_another_job_opened(session: Session, tenant_id: UUID, source_id: UUID) -> None:
    try:
        session.commit()
    except IntegrityError:
        # Another request opened a job between the check and this commit.
        session.rollback()
        open_job_id = _open_job_id(session, tenant_id, source_id)
        if open_job_id is None:
            raise
        raise JobAlreadyOpen(open_job_id) from None


def _open_job_id(session: Session, tenant_id: UUID, source_id: UUID) -> UUID | None:
    return session.scalars(
        select(IngestionJob.id).where(
            IngestionJob.tenant_id == tenant_id,
            IngestionJob.source_id == source_id,
            IngestionJob.status.in_(OPEN_JOB_STATUSES),
        )
    ).first()
