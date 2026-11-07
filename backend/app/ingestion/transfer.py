"""The Kaggle route (spec section 5): export a waiting job's chunks, embed them elsewhere,
then import the vectors and publish them with step 7.

A job waits for the versions it marked with awaiting_job_id, not for every unembedded chunk
in its source: a version whose publish failed in an earlier job also has unembedded chunks,
and publishing it would replace a newer current version. The mark stays until the whole
import finishes, so an import that fails partway can run again with the same files.
"""

import json
from pathlib import Path
from typing import Any
from uuid import UUID

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.config import Settings
from app.db.constants import JobStatus
from app.db.models import Chunk, DocumentVersion, IngestionJob
from app.db.vector_index import VectorIndex
from app.embedding.base import embedding_text
from app.ingestion.pipeline import publish_version


class TransferError(Exception):
    """The job, the export or the import folder can't be used. The message says why."""


def export_chunks(session: Session, job_id: UUID, out_path: Path, settings: Settings) -> int:
    """Write the job's waiting chunks as JSONL after a manifest line. Returns the count."""
    job = _waiting_job(session, job_id)
    chunks = session.scalars(
        select(Chunk)
        .join(DocumentVersion, Chunk.document_version_id == DocumentVersion.id)
        .where(
            DocumentVersion.tenant_id == job.tenant_id,
            DocumentVersion.awaiting_job_id == job.id,
            Chunk.tenant_id == job.tenant_id,
        )
        .order_by(DocumentVersion.created_at, Chunk.document_version_id, Chunk.position)
    ).all()
    manifest = {**_model(settings), "chunk_count": len(chunks)}

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    partial = out_path.with_name(out_path.name + ".partial")
    with partial.open("w", encoding="utf-8", newline="\n") as file:
        file.write(json.dumps({"manifest": manifest}) + "\n")
        for chunk in chunks:
            text = embedding_text(tuple(chunk.heading_path), chunk.content)
            line = {"chunk_id": str(chunk.id), "text": text}
            file.write(json.dumps(line, ensure_ascii=False) + "\n")
    partial.replace(out_path)
    return len(chunks)


def import_vectors(
    session: Session, job_id: UUID, in_dir: Path, index: VectorIndex, settings: Settings
) -> None:
    """Check the folder against the job, publish every waiting version, then finish the job.

    Everything is checked before anything is written to Qdrant.
    """
    job = _waiting_job(session, job_id)
    in_dir = Path(in_dir)
    manifest = _read_manifest(in_dir)
    _check_model(manifest, settings)
    vectors = _read_shards(in_dir, settings.embedding_dimension)
    if manifest["chunk_count"] != len(vectors):
        raise TransferError(
            f"manifest.json gives a chunk count of {manifest['chunk_count']}, "
            f"but the shards hold {len(vectors)} chunks"
        )

    versions = session.scalars(
        select(DocumentVersion)
        .where(
            DocumentVersion.tenant_id == job.tenant_id,
            DocumentVersion.awaiting_job_id == job.id,
        )
        .order_by(DocumentVersion.created_at, DocumentVersion.id)
    ).all()
    expected: dict[UUID, UUID] = dict(
        session.execute(
            select(Chunk.id, Chunk.document_version_id).where(
                Chunk.tenant_id == job.tenant_id,
                Chunk.document_version_id.in_([version.id for version in versions]),
            )
        ).all()
    )
    missing = expected.keys() - vectors.keys()
    if missing:
        raise TransferError(
            f"{len(missing)} waiting chunks are missing from the shards, for example {min(missing)}"
        )
    unknown = vectors.keys() - expected.keys()
    if unknown:
        raise TransferError(
            f"{len(unknown)} chunk ids in the shards are unknown or not waiting for job "
            f"{job.id}, for example {min(unknown)}"
        )

    for version in versions:
        version_vectors = {
            chunk_id: vectors[chunk_id]
            for chunk_id, version_id in expected.items()
            if version_id == version.id
        }
        try:
            publish_version(
                session,
                version,
                version_vectors,
                index,
                settings.embedding_model_id,
                retry_wait=settings.retry_wait_seconds,
            )
        except Exception as error:
            session.rollback()
            raise TransferError(
                f"could not publish the vectors ({type(error).__name__}: {error}). "
                "Nothing is lost: run import-vectors again with the same folder to finish"
            ) from error

    session.execute(
        update(DocumentVersion)
        .where(DocumentVersion.awaiting_job_id == job.id)
        .values(awaiting_job_id=None)
    )
    job.status = JobStatus.PARTIAL if job.errors else JobStatus.SUCCEEDED
    job.finished_at = func.now()
    session.commit()


def _waiting_job(session: Session, job_id: UUID) -> IngestionJob:
    job = session.get(IngestionJob, job_id)
    if job is None:
        raise TransferError(f"job {job_id} not found")
    if job.status != JobStatus.AWAITING_EMBEDDING:
        raise TransferError(f"job {job_id} is {job.status}, not awaiting embedding")
    return job


def _model(settings: Settings) -> dict[str, Any]:
    return {
        "model_id": settings.embedding_model_id,
        "model_revision": settings.embedding_model_revision,
        "dimension": settings.embedding_dimension,
    }


def _read_manifest(in_dir: Path) -> dict[str, Any]:
    path = in_dir / "manifest.json"
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise TransferError(f"{path} is missing or isn't valid JSON") from error
    fields = {"model_id": str, "model_revision": str, "dimension": int, "chunk_count": int}
    for name, kind in fields.items():
        if not isinstance(manifest, dict) or not isinstance(manifest.get(name), kind):
            raise TransferError(f"manifest.json needs {name}")
    return manifest


def _check_model(manifest: dict[str, Any], settings: Settings) -> None:
    for field, label in (
        ("model_id", "model id"),
        ("model_revision", "model revision"),
        ("dimension", "dimension"),
    ):
        expected = _model(settings)[field]
        if manifest[field] != expected:
            raise TransferError(
                f"manifest.json has {label} {manifest[field]}, but this server uses {expected}"
            )


def _read_shards(in_dir: Path, dimension: int) -> dict[UUID, list[float]]:
    paths = sorted(in_dir.glob("vectors-*.parquet"))
    if not paths:
        raise TransferError(f"no vectors-*.parquet files in {in_dir}")
    vectors: dict[UUID, list[float]] = {}
    for path in paths:
        try:
            table = pq.read_table(path, columns=["chunk_id", "vector"])
            column = table.column("vector")
            lengths = pc.list_value_length(column)
            wrong_length = pc.any(pc.not_equal(lengths, dimension)).as_py()
            finite = pc.all(pc.is_finite(pc.list_flatten(column))).as_py()
        except (pa.ArrowException, OSError, ValueError, KeyError) as error:
            raise TransferError(
                f"{path.name} isn't a shard of chunk_id and vector columns"
            ) from error
        if column.null_count or wrong_length:
            raise TransferError(f"{path.name} has a vector length other than {dimension}")
        if finite is False:
            raise TransferError(f"{path.name} has vector values that aren't finite numbers")
        for raw_id, vector in zip(
            table.column("chunk_id").to_pylist(), column.to_pylist(), strict=True
        ):
            try:
                chunk_id = UUID(raw_id)
            except (TypeError, ValueError, AttributeError) as error:
                raise TransferError(f"{path.name} has a chunk_id that isn't a UUID") from error
            if chunk_id in vectors:
                raise TransferError(f"chunk {chunk_id} appears more than once in the shards")
            vectors[chunk_id] = vector
    return vectors
