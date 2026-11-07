from uuid import uuid5

import pytest
from sqlalchemy import func, select

from app.db.constants import DEFAULT_TENANT_ID, DEFAULT_UPLOAD_SOURCE_ID
from app.db.models import Chunk, DocumentVersion, Source
from app.ingestion.jobs import JobAlreadyOpen, create_job, mark_interrupted_jobs
from app.ingestion.pipeline import run_ingestion
from tests.fakes import ExplodingConnector


def test_upload_creates_version_and_chunks(session, ingest):
    job = ingest({"guide.md": b"# A\nhello world\n"}, defer_embedding=True)
    assert job.status == "awaiting_embedding"
    assert job.file_counts == {"processed": 1, "skipped": 0, "failed": 0}
    chunk = session.scalars(select(Chunk)).one()
    assert chunk.tenant_id == DEFAULT_TENANT_ID and chunk.embedded_at is None


def test_chunk_ids_derive_from_version_and_position(session, ingest):
    ingest({"guide.md": b"# A\nhello\n"}, defer_embedding=True)
    chunk = session.scalars(select(Chunk)).one()
    assert chunk.id == uuid5(chunk.document_version_id, "0")


def test_unchanged_published_file_is_skipped(session, ingest, publish_all):
    ingest({"guide.md": b"# A\nx\n"}, defer_embedding=True)
    publish_all()
    job = ingest({"guide.md": b"# A\nx\n"}, defer_embedding=True)
    assert job.status == "succeeded" and job.file_counts["skipped"] == 1
    assert session.scalar(select(func.count()).select_from(DocumentVersion)) == 1


def test_changed_file_creates_new_version(session, ingest, publish_all):
    ingest({"guide.md": b"# A\nx\n"}, defer_embedding=True)
    publish_all()
    ingest({"guide.md": b"# A\ny\n"}, defer_embedding=True)
    assert session.scalar(select(func.count()).select_from(DocumentVersion)) == 2


def test_rerun_of_unpublished_version_adds_nothing(session, ingest, finish_job):
    ingest({"guide.md": b"# A\nx\n"}, defer_embedding=True)
    finish_job()
    job = ingest({"guide.md": b"# A\nx\n"}, defer_embedding=True)
    assert job.status == "awaiting_embedding" and job.file_counts["processed"] == 1
    assert session.scalar(select(func.count()).select_from(Chunk)) == 1


def test_bad_file_is_recorded_and_job_continues(ingest):
    job = ingest({"good.md": b"# A\nx\n", "bad.md": b"   "}, defer_embedding=True)
    assert job.status == "awaiting_embedding"
    assert job.file_counts == {"processed": 1, "skipped": 0, "failed": 1}
    assert job.errors == [{"path": "bad.md", "reason": "no text"}]


def test_some_failures_with_nothing_waiting_is_partial(ingest, publish_all):
    ingest({"good.md": b"# A\nx\n"}, defer_embedding=True)
    publish_all()
    job = ingest({"good.md": b"# A\nx\n", "bad.md": b"   "}, defer_embedding=True)
    assert job.status == "partial"
    assert job.file_counts == {"processed": 0, "skipped": 1, "failed": 1}


def test_all_files_bad_fails_the_job(ingest):
    assert ingest({"bad.md": b"   "}, defer_embedding=True).status == "failed"


def test_no_files_fails_with_a_reason(ingest):
    job = ingest({}, defer_embedding=True)
    assert job.status == "failed"
    assert job.errors == [{"path": "", "reason": "no supported files found"}]


def test_connector_error_fails_the_job_with_its_message(ingest_with, failing_connector):
    job = ingest_with(failing_connector("Repository not found or private"))
    assert job.status == "failed"
    assert job.errors[0]["reason"] == "Repository not found or private"


def test_connector_is_closed_after_an_error(ingest_with, failing_connector):
    connector = failing_connector("Repository not found or private")
    ingest_with(connector)
    assert connector.closed


def test_unexpected_error_fails_the_job_instead_of_leaving_it_running(ingest_with):
    job = ingest_with(ExplodingConnector())
    assert job.status == "failed" and job.finished_at is not None
    assert job.errors == [{"path": "", "reason": "internal error"}]


def test_job_that_is_not_pending_is_not_started(session, make_job, deps):
    job = make_job(status="succeeded")
    run_ingestion(job.id, deps)
    session.refresh(job)
    assert job.started_at is None


def test_mark_interrupted_covers_pending_and_running(session, make_job):
    job = make_job(status="running")
    assert mark_interrupted_jobs(session) == 1
    session.refresh(job)
    assert job.status == "interrupted"


def test_create_job_refuses_a_second_open_job(session, make_job):
    open_job = make_job(status="awaiting_embedding")
    with pytest.raises(JobAlreadyOpen) as raised:
        create_job(session, session.get(Source, DEFAULT_UPLOAD_SOURCE_ID), {"uploads": []})
    assert raised.value.job_id == open_job.id
