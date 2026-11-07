"""The notebook's first cell, run here with exec, so the test needs no Kaggle or GPU."""

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import NAMESPACE_URL, uuid5

import pyarrow.parquet as pq
import pytest

from app.ingestion.transfer import export_chunks, import_vectors
from tests.fakes import FakeEmbedder

NOTEBOOK = Path(__file__).resolve().parents[2] / "notebooks" / "kaggle_embed.ipynb"


@pytest.fixture(scope="module")
def notebook():
    cells = json.loads(NOTEBOOK.read_text(encoding="utf-8"))["cells"]
    source = "".join(next(cell for cell in cells if cell["cell_type"] == "code")["source"])
    namespace: dict = {}
    exec(compile(source, str(NOTEBOOK), "exec"), namespace)
    return SimpleNamespace(**namespace)


@pytest.fixture
def chunks_file(tmp_path, settings):
    """An export of `count` chunks with stable ids, like export-chunks writes."""

    def write(count: int, folder: Path | None = None) -> Path:
        path = (folder or tmp_path) / "chunks.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        manifest = {
            "model_id": settings.embedding_model_id,
            "model_revision": settings.embedding_model_revision,
            "dimension": settings.embedding_dimension,
            "chunk_count": count,
        }
        lines = [json.dumps({"manifest": manifest})]
        lines += [
            json.dumps({"chunk_id": str(uuid5(NAMESPACE_URL, str(i))), "text": f"chunk {i}"})
            for i in range(count)
        ]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path

    return write


def zeros(texts):
    return [[0.0] * 1024 for _ in texts]


def test_notebook_writes_shards_and_skips_finished_ones(tmp_path, notebook, chunks_file):
    encode = Mock(side_effect=zeros)
    notebook.run(chunks_file(5), tmp_path, encode, shard_size=2, done_dirs=[tmp_path])
    calls = encode.call_count
    notebook.run(chunks_file(5), tmp_path, encode, shard_size=2, done_dirs=[tmp_path])
    assert encode.call_count == calls
    assert len(list(tmp_path.glob("vectors-*.parquet"))) == 3


def test_shards_hold_every_chunk_in_order(tmp_path, notebook, chunks_file):
    out = tmp_path / "out"
    notebook.run(chunks_file(5), out, Mock(side_effect=zeros), shard_size=2, done_dirs=[out])
    ids = []
    for shard in sorted(out.glob("vectors-*.parquet")):
        table = pq.read_table(shard)
        ids += table.column("chunk_id").to_pylist()
        assert all(len(vector) == 1024 for vector in table.column("vector").to_pylist())
    assert ids == [str(uuid5(NAMESPACE_URL, str(i))) for i in range(5)]


def test_manifest_is_copied_from_the_export(tmp_path, notebook, chunks_file):
    out = tmp_path / "out"
    chunks = chunks_file(3)
    notebook.run(chunks, out, Mock(side_effect=zeros), shard_size=2, done_dirs=[out])
    exported = json.loads(chunks.read_text(encoding="utf-8").splitlines()[0])["manifest"]
    assert json.loads((out / "manifest.json").read_text(encoding="utf-8")) == exported


def test_shards_from_an_earlier_session_are_copied_not_encoded(tmp_path, notebook, chunks_file):
    earlier, out = tmp_path / "earlier", tmp_path / "out"
    chunks = chunks_file(4)
    notebook.run(chunks, earlier, Mock(side_effect=zeros), shard_size=2, done_dirs=[earlier])
    encode = Mock(side_effect=zeros)
    notebook.run(chunks, out, encode, shard_size=2, done_dirs=[out, earlier])
    assert encode.call_count == 0
    assert sorted(p.name for p in out.glob("vectors-*.parquet")) == [
        "vectors-00000.parquet",
        "vectors-00001.parquet",
    ]


def test_a_shard_for_other_chunks_is_encoded_again(tmp_path, notebook, chunks_file):
    out = tmp_path / "out"
    notebook.run(chunks_file(2), out, Mock(side_effect=zeros), shard_size=2, done_dirs=[out])
    encode = Mock(side_effect=zeros)
    notebook.run(chunks_file(3), out, encode, shard_size=3, done_dirs=[out])
    assert encode.call_count == 1


def test_shards_left_from_a_longer_export_are_removed(tmp_path, notebook, chunks_file):
    out = tmp_path / "out"
    notebook.run(chunks_file(5), out, Mock(side_effect=zeros), shard_size=2, done_dirs=[out])
    notebook.run(chunks_file(2), out, Mock(side_effect=zeros), shard_size=2, done_dirs=[out])
    assert [p.name for p in out.glob("vectors-*.parquet")] == ["vectors-00000.parquet"]


def test_wrong_vector_length_stops_the_run(tmp_path, notebook, chunks_file):
    encode = Mock(side_effect=lambda texts: [[0.0] * 3 for _ in texts])
    with pytest.raises(ValueError, match="1024"):
        notebook.run(chunks_file(2), tmp_path, encode, shard_size=2, done_dirs=[tmp_path])
    assert list(tmp_path.glob("vectors-*.parquet")) == []


def test_export_notebook_import_round_trip(
    session, deferred_job, notebook, index, settings, tmp_path
):
    chunks = tmp_path / "chunks.jsonl"
    export_chunks(session, deferred_job.id, chunks, settings)
    embedder = FakeEmbedder()
    out = tmp_path / "out"

    def encode(texts):
        return embedder.embed_passages(texts, 8)

    notebook.run(chunks, out, encode, shard_size=1000, done_dirs=[out])
    import_vectors(session, deferred_job.id, out, index, settings)
    session.refresh(deferred_job)
    assert deferred_job.status == "succeeded" and index.count() == 1
