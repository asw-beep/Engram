from pathlib import PurePosixPath
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile

from app.api.deps import ScopeDep, ServicesDep, SessionDep
from app.api.schemas import JobAccepted, SourceOut
from app.ingestion.jobs import JobAlreadyOpen, create_upload_job, get_source, list_sources
from app.ingestion.parsers import SUPPORTED_EXTENSIONS
from app.ingestion.pipeline import run_ingestion

router = APIRouter(prefix="/api/sources")


@router.get("", response_model=list[SourceOut])
def read_sources(session: SessionDep, scope: ScopeDep):
    return list_sources(session, scope.tenant_id)


@router.post("/{source_id}/documents", status_code=202, response_model=JobAccepted)
def upload_documents(
    source_id: UUID,
    background: BackgroundTasks,
    files: Annotated[list[UploadFile], File()],
    session: SessionDep,
    services: ServicesDep,
    scope: ScopeDep,
    defer_embedding: Annotated[bool, Form()] = False,
) -> JobAccepted:
    source = get_source(session, scope.tenant_id, source_id)
    if source is None:
        raise HTTPException(404, "Source not found")
    if source.type != "upload":
        raise HTTPException(400, "Files can only be uploaded to an upload source")

    # Check every file before saving any of them.
    limit = services.settings.max_upload_bytes
    accepted: list[tuple[str, bytes]] = []
    for upload in files:
        name = _base_name(upload.filename or "")
        if PurePosixPath(name).suffix.lower() not in SUPPORTED_EXTENSIONS:
            allowed = ", ".join(sorted(SUPPORTED_EXTENSIONS))
            raise HTTPException(
                415, f"Unsupported file type: {name or 'unnamed file'}. Use {allowed}"
            )
        content = upload.file.read(limit + 1)
        if len(content) > limit:
            raise HTTPException(413, f"File too large: {name} is over {limit // 2**20} MB")
        if any(name == seen for seen, _ in accepted):
            raise HTTPException(400, f"Two files are named {name}. Upload them separately")
        accepted.append((name, content))

    try:
        job = create_upload_job(session, services.file_store, source, accepted, defer_embedding)
    except JobAlreadyOpen as error:
        raise HTTPException(
            409, {"message": "This source already has an open job", "job_id": str(error.job_id)}
        ) from None
    background.add_task(run_ingestion, job.id, services)
    return JobAccepted(job_id=job.id)


def _base_name(filename: str) -> str:
    """Keep only the last path part, whichever separator the client used."""
    return PurePosixPath(filename.replace("\\", "/")).name
