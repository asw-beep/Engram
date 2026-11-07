from sqlalchemy import select

from app.db.models import Chunk, Document


def current_version(session, path):
    return session.scalars(select(Document.current_version_id).where(Document.path == path)).one()


def test_job_publishes_and_succeeds(session, ingest, index):
    job = ingest({"guide.md": b"# A\nhello\n"})
    assert job.status == "succeeded" and index.count() == 1
    chunk = session.scalars(select(Chunk)).one()
    assert chunk.embedding_model == "BAAI/bge-m3" and chunk.embedded_at is not None


def test_new_version_replaces_old_points(ingest, index):
    ingest({"guide.md": b"# A\nold\n"})
    ingest({"guide.md": b"# A\nnew\n"})
    assert index.count() == 1


def test_failed_publish_keeps_old_version_and_retry_finishes(
    session, ingest, retry, index, fail_upserts
):
    ingest({"guide.md": b"# A\nold\n"})
    old = current_version(session, "guide.md")
    with fail_upserts(times=4):
        job = ingest({"guide.md": b"# A\nnew\n"})
    assert job.status == "failed" and current_version(session, "guide.md") == old
    assert retry(job).status == "succeeded"
    assert current_version(session, "guide.md") != old and index.count() == 1


def test_reverting_to_earlier_content_republishes_it(session, ingest, index):
    ingest({"guide.md": b"# A\nfirst\n"})
    first = current_version(session, "guide.md")
    ingest({"guide.md": b"# A\nsecond\n"})
    job = ingest({"guide.md": b"# A\nfirst\n"})
    assert job.status == "succeeded"
    assert current_version(session, "guide.md") == first and index.count() == 1


def test_deferred_job_waits_for_embedding(ingest, index):
    job = ingest({"guide.md": b"# A\nx\n"}, defer_embedding=True)
    assert job.status == "awaiting_embedding" and index.count() == 0


def test_deferring_a_previously_published_version_marks_its_chunks_waiting(session, ingest):
    ingest({"guide.md": b"# A\nfirst\n"})
    first = current_version(session, "guide.md")
    ingest({"guide.md": b"# A\nsecond\n"})
    job = ingest({"guide.md": b"# A\nfirst\n"}, defer_embedding=True)
    assert job.status == "awaiting_embedding"
    embedded_at = session.scalars(
        select(Chunk.embedded_at).where(Chunk.document_version_id == first)
    ).all()
    assert embedded_at == [None]
