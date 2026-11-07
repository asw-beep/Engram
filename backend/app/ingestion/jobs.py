from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.constants import OPEN_JOB_STATUSES, JobStatus
from app.db.models import IngestionJob, Source


class JobAlreadyOpen(Exception):
    def __init__(self, job_id: UUID):
        super().__init__(f"job {job_id} is still open for this source")
        self.job_id = job_id


def create_job(session: Session, source: Source, input: dict) -> IngestionJob:
    """Add a pending job, unless the source already has an open one."""
    open_job_id = _open_job_id(session, source)
    if open_job_id is not None:
        raise JobAlreadyOpen(open_job_id)
    job = IngestionJob(
        tenant_id=source.tenant_id, source_id=source.id, status=JobStatus.PENDING, input=input
    )
    session.add(job)
    try:
        session.commit()
    except IntegrityError:
        # Another request opened a job between the check and the insert.
        session.rollback()
        open_job_id = _open_job_id(session, source)
        if open_job_id is None:
            raise
        raise JobAlreadyOpen(open_job_id) from None
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


def _open_job_id(session: Session, source: Source) -> UUID | None:
    return session.scalars(
        select(IngestionJob.id).where(
            IngestionJob.tenant_id == source.tenant_id,
            IngestionJob.source_id == source.id,
            IngestionJob.status.in_(OPEN_JOB_STATUSES),
        )
    ).first()
