from uuid import UUID

from sqlalchemy import select

from app.api.deps import get_current_tenant
from app.db.models import Chunk, Document
from tests.fakes import FailingKeywordIndex


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


def keyword_entries(keyword_index):
    """Every entry in the keyword index, by chunk ID."""
    response = keyword_index.client.search(
        index=keyword_index.index, body={"query": {"match_all": {}}, "size": 100}
    )
    return {UUID(hit["_id"]): hit["_source"] for hit in response["hits"]["hits"]}


def test_publishing_saves_the_chunk_text_to_the_keyword_index(session, ingest, keyword_index):
    ingest({"guide.md": b"# Setup\n## Install\nRun the installer twice.\n"})
    chunk = session.scalars(select(Chunk)).one()
    document = session.scalars(select(Document)).one()
    assert keyword_entries(keyword_index) == {
        chunk.id: {
            "content": chunk.content,
            "headings": "Setup > Install",
            "tenant_id": str(document.tenant_id),
            "document_id": str(document.id),
            "document_version_id": str(document.current_version_id),
            "allowed_principals": list(document.allowed_principals),
        }
    }
    hits = keyword_index.search("installer", get_current_tenant(), 10)
    assert [chunk_id for chunk_id, _ in hits] == [chunk.id]


def test_a_failed_keyword_upsert_keeps_the_old_version_and_retry_finishes(
    session, ingest, retry, index, keyword_index
):
    ingest({"guide.md": b"# A\nold\n"})
    old = current_version(session, "guide.md")
    job = ingest({"guide.md": b"# A\nnew\n"}, keyword_index=FailingKeywordIndex())
    assert job.status == "failed"
    assert job.errors == [
        {"path": "guide.md", "reason": "could not save text to the keyword index"}
    ]
    assert current_version(session, "guide.md") == old
    assert [entry["document_version_id"] for entry in keyword_entries(keyword_index).values()] == [
        str(old)
    ]
    assert retry(job).status == "succeeded"
    assert current_version(session, "guide.md") != old
    assert index.count() == 1 and keyword_index.count() == 1


def test_a_new_version_replaces_the_old_text_in_the_keyword_index(session, ingest, keyword_index):
    ingest({"guide.md": b"# A\nold\n"})
    ingest({"guide.md": b"# A\nnew\n"})
    new = current_version(session, "guide.md")
    assert [entry["document_version_id"] for entry in keyword_entries(keyword_index).values()] == [
        str(new)
    ]


def test_a_failed_keyword_delete_still_publishes_and_clears_qdrant(
    session, ingest, index, keyword_index, monkeypatch
):
    ingest({"guide.md": b"# A\nold\n"})
    old = current_version(session, "guide.md")

    def refuse(version_id):
        raise ConnectionError("OpenSearch is unavailable (test)")

    monkeypatch.setattr(keyword_index, "delete_version", refuse)
    job = ingest({"guide.md": b"# A\nnew\n"})
    assert job.status == "succeeded" and current_version(session, "guide.md") != old
    assert index.count() == 1


def test_a_failed_qdrant_delete_still_clears_the_keyword_index(
    session, ingest, index, keyword_index, monkeypatch
):
    ingest({"guide.md": b"# A\nold\n"})

    def refuse(version_id):
        raise ConnectionError("Qdrant is unavailable (test)")

    monkeypatch.setattr(index, "delete_version", refuse)
    job = ingest({"guide.md": b"# A\nnew\n"})
    assert job.status == "succeeded" and keyword_index.count() == 1


def test_published_text_carries_the_documents_own_principals(session, ingest, keyword_index):
    ingest({"guide.md": b"# A\nold\n"})
    document = session.scalars(select(Document)).one()
    document.allowed_principals = ["group:sre"]
    session.commit()
    ingest({"guide.md": b"# A\nnew\n"})
    entries = list(keyword_entries(keyword_index).values())
    assert [entry["allowed_principals"] for entry in entries] == [["group:sre"]]
