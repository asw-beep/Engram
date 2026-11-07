import json
from uuid import uuid4

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from sqlalchemy import select, text

from app.cli import run_cli
from app.db.models import Chunk, DocumentVersion
from app.embedding.base import embedding_text
from app.ingestion.transfer import TransferError, export_chunks, import_vectors


def test_export_writes_manifest_and_embedding_text(session, deferred_job, tmp_path, settings):
    out = tmp_path / "chunks.jsonl"
    assert export_chunks(session, deferred_job.id, out, settings) == 1
    first, second = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    assert first["manifest"] == {
        "model_id": settings.embedding_model_id,
        "model_revision": settings.embedding_model_revision,
        "dimension": settings.embedding_dimension,
        "chunk_count": 1,
    }
    chunk = session.scalars(select(Chunk)).one()
    assert second == {"chunk_id": str(chunk.id), "text": embedding_text(("A",), chunk.content)}
    assert second["text"].startswith("A\n\n")


def test_export_requires_a_waiting_job(session, make_job, tmp_path, settings):
    with pytest.raises(TransferError, match="not awaiting embedding"):
        export_chunks(session, make_job(status="succeeded").id, tmp_path / "x", settings)


def test_export_of_an_unknown_job_is_an_error(session, tmp_path, settings):
    with pytest.raises(TransferError, match="not found"):
        export_chunks(session, uuid4(), tmp_path / "x", settings)


def test_export_leaves_out_versions_the_job_did_not_save(
    session, deferred_job, make_version, make_chunk, tmp_path, settings
):
    # A version whose publish failed in an earlier job also has unembedded chunks.
    abandoned = make_version()
    make_chunk(abandoned, content="old text")
    assert export_chunks(session, deferred_job.id, tmp_path / "chunks.jsonl", settings) == 1


def test_import_publishes_and_finishes_the_job(session, deferred_job, shards, index, settings):
    import_vectors(session, deferred_job.id, shards(), index, settings)
    session.refresh(deferred_job)
    assert deferred_job.status == "succeeded" and index.count() == 1
    assert deferred_job.finished_at is not None
    chunk = session.scalars(select(Chunk)).one()
    assert chunk.embedded_at is not None and chunk.embedding_model == settings.embedding_model_id
    version = session.get(DocumentVersion, chunk.document_version_id)
    assert version.awaiting_job_id is None


def test_imported_document_answers_questions(
    client, deferred_job, shards, index, settings, session, fake_llm
):
    import_vectors(session, deferred_job.id, shards(), index, settings)
    fake_llm.returns("answered", "Hello [1].")
    response = client.post("/api/questions", json={"question": "A hello"}).json()
    assert response["outcome"] == "answered"


def test_import_keeps_partial_when_files_failed_earlier(
    session, deferred_partial_job, shards, index, settings
):
    import_vectors(session, deferred_partial_job.id, shards(), index, settings)
    session.refresh(deferred_partial_job)
    assert deferred_partial_job.status == "partial"


def test_import_can_run_again_after_a_partial_publish(
    session, ingest, shards, index, settings, monkeypatch
):
    job = ingest({"a.md": b"# A\nhello\n", "b.md": b"# B\nworld\n"}, defer_embedding=True)
    files = shards()
    real_upsert = index.upsert
    calls = []

    def first_only(points):
        calls.append(points)
        if len(calls) > 1:
            raise ConnectionError("Qdrant is unavailable (test)")
        real_upsert(points)

    monkeypatch.setattr(index, "upsert", first_only)
    with pytest.raises(TransferError, match="run import-vectors again"):
        import_vectors(session, job.id, files, index, settings)
    monkeypatch.setattr(index, "upsert", real_upsert)
    session.refresh(job)
    assert job.status == "awaiting_embedding" and index.count() == 1

    import_vectors(session, job.id, files, index, settings)
    session.refresh(job)
    assert job.status == "succeeded" and index.count() == 2


def test_import_can_run_again_after_a_database_error(
    session, deferred_job, shards, index, settings, monkeypatch
):
    files = shards()
    real_commit = session.commit

    def failing_commit():
        monkeypatch.setattr(session, "commit", real_commit)
        session.execute(text("SELECT 1 / 0"))

    monkeypatch.setattr(session, "commit", failing_commit)
    with pytest.raises(TransferError, match="run import-vectors again"):
        import_vectors(session, deferred_job.id, files, index, settings)
    import_vectors(session, deferred_job.id, files, index, settings)
    session.refresh(deferred_job)
    assert deferred_job.status == "succeeded"


def test_import_ignores_versions_the_job_did_not_save(
    session, deferred_job, shards, make_version, make_chunk, index, settings
):
    files = shards()
    make_chunk(make_version(), content="old text")
    import_vectors(session, deferred_job.id, files, index, settings)
    session.refresh(deferred_job)
    assert deferred_job.status == "succeeded"


@pytest.mark.parametrize(
    "change, message",
    [
        ({"model_revision": "other"}, "model revision"),
        ({"model_id": "other/model"}, "model id"),
        ({"dimension": 768}, "dimension"),
        ({"chunk_count": 5}, "chunk count"),
    ],
)
def test_import_rejects_a_wrong_manifest(
    session, deferred_job, shards, index, settings, change, message
):
    with pytest.raises(TransferError, match=message):
        import_vectors(session, deferred_job.id, shards(manifest=change), index, settings)
    assert index.count() == 0


def test_import_rejects_a_manifest_field_of_the_wrong_type(
    session, deferred_job, shards, index, settings
):
    with pytest.raises(TransferError, match="needs chunk_count"):
        import_vectors(
            session, deferred_job.id, shards(manifest={"chunk_count": "one"}), index, settings
        )


def test_import_rejects_a_chunk_id_that_is_not_a_uuid(
    session, deferred_job, shards, index, settings
):
    folder = shards()
    table = pa.table({"chunk_id": ["nope"], "vector": [[1.0] * 1024]})
    pq.write_table(table, folder / "vectors-00000.parquet")
    with pytest.raises(TransferError, match="isn't a UUID"):
        import_vectors(session, deferred_job.id, folder, index, settings)


def test_import_rejects_a_shard_without_vectors(session, deferred_job, shards, index, settings):
    folder = shards()
    pq.write_table(pa.table({"chunk_id": ["x"]}), folder / "vectors-00000.parquet")
    with pytest.raises(TransferError, match="chunk_id and vector"):
        import_vectors(session, deferred_job.id, folder, index, settings)


def test_import_rejects_a_missing_manifest(session, deferred_job, shards, index, settings):
    folder = shards()
    (folder / "manifest.json").unlink()
    with pytest.raises(TransferError, match="manifest.json"):
        import_vectors(session, deferred_job.id, folder, index, settings)


def test_import_rejects_a_folder_without_shards(session, deferred_job, shards, index, settings):
    folder = shards()
    for shard in folder.glob("vectors-*.parquet"):
        shard.unlink()
    with pytest.raises(TransferError, match="vectors-"):
        import_vectors(session, deferred_job.id, folder, index, settings)


def test_import_rejects_missing_chunks(session, deferred_job, shards, index, settings):
    with pytest.raises(TransferError, match="missing"):
        import_vectors(session, deferred_job.id, shards(drop=1), index, settings)
    session.refresh(deferred_job)
    assert deferred_job.status == "awaiting_embedding"
    assert index.count() == 0


def test_import_rejects_unknown_chunks(session, deferred_job, shards, index, settings):
    with pytest.raises(TransferError, match="unknown"):
        import_vectors(session, deferred_job.id, shards(extra=1), index, settings)
    assert index.count() == 0


def test_import_rejects_a_chunk_twice(session, deferred_job, shards, index, settings):
    with pytest.raises(TransferError, match="more than once"):
        import_vectors(session, deferred_job.id, shards(repeat=True), index, settings)


def test_import_rejects_wrong_vector_length(session, deferred_job, shards, index, settings):
    with pytest.raises(TransferError, match="vector length"):
        import_vectors(session, deferred_job.id, shards(vector_length=3), index, settings)
    assert index.count() == 0


def test_import_rejects_values_that_are_not_finite(session, deferred_job, shards, index, settings):
    with pytest.raises(TransferError, match="finite"):
        import_vectors(session, deferred_job.id, shards(fill=float("nan")), index, settings)


def test_import_requires_a_waiting_job(session, make_job, shards, index, settings):
    job = make_job(status="succeeded")
    with pytest.raises(TransferError, match="not awaiting embedding"):
        import_vectors(session, job.id, shards(), index, settings)


def test_cli_exports_and_imports(
    deferred_job, shards, tmp_path, settings, session_factory, index, session, capsys
):
    out = tmp_path / "out" / "chunks.jsonl"
    args = ["export-chunks", "--job", str(deferred_job.id), "--out", str(out)]
    assert run_cli(args, settings, session_factory, index) == 0
    assert "1 chunk" in capsys.readouterr().out
    args = ["import-vectors", "--job", str(deferred_job.id), "--in", str(shards())]
    assert run_cli(args, settings, session_factory, index) == 0
    session.refresh(deferred_job)
    assert deferred_job.status == "succeeded"


def test_cli_reports_a_transfer_error(settings, session_factory, index, tmp_path, capsys):
    args = ["export-chunks", "--job", str(uuid4()), "--out", str(tmp_path / "x")]
    assert run_cli(args, settings, session_factory, index) == 1
    assert "not found" in capsys.readouterr().err
