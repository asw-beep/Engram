from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import ScopeDep, ServicesDep, SessionDep
from app.api.schemas import JobAccepted, JobOut
from app.db.models import IngestionJob
from app.ingestion.jobs import JobAlreadyOpen, JobNotRetryable, get_job, list_jobs, retry_job
from app.ingestion.pipeline import run_ingestion
from app.types import AccessScope

router = APIRouter(prefix="/api/jobs")


@router.get("", response_model=list[JobOut])
def read_jobs(session: SessionDep, scope: ScopeDep):
    return list_jobs(session, scope.tenant_id, limit=50)


@router.get("/{job_id}", response_model=JobOut)
def read_job(
    job_id: UUID,
    session: SessionDep,
    scope: ScopeDep,
):
    return _job_or_404(session, scope, job_id)


@router.post("/{job_id}/retry", status_code=202, response_model=JobAccepted)
def retry(
    job_id: UUID,
    background: BackgroundTasks,
    session: SessionDep,
    services: ServicesDep,
    scope: ScopeDep,
) -> JobAccepted:
    job = _job_or_404(session, scope, job_id)
    try:
        retry_job(session, job)
    except JobNotRetryable as error:
        raise HTTPException(409, str(error)) from None
    except JobAlreadyOpen as error:
        raise HTTPException(
            409, {"message": "This source already has an open job", "job_id": str(error.job_id)}
        ) from None
    background.add_task(run_ingestion, job.id, services)
    return JobAccepted(job_id=job.id)


def _job_or_404(session: Session, scope: AccessScope, job_id: UUID) -> IngestionJob:
    job = get_job(session, scope.tenant_id, job_id)
    if job is None:
        raise HTTPException(404, "Job not found")
    return job
