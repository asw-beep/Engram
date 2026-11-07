"""Recheck every hit against Postgres before its text is used (spec section 7, Plan.md 6.7).

Qdrant filters by tenant and principals already, but Postgres is canonical: a hit survives
only if its chunk belongs to the caller's tenant, sits in its document's current version,
and the document shares a principal with the caller.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Chunk, Document, DocumentVersion, Source
from app.types import AccessScope, Passage, RetrievalHit


def load_passages(session: Session, hits: list[RetrievalHit], scope: AccessScope) -> list[Passage]:
    if not hits:
        return []
    rows = session.execute(
        select(Chunk, DocumentVersion, Document, Source)
        .join(DocumentVersion, DocumentVersion.id == Chunk.document_version_id)
        .join(Document, Document.current_version_id == Chunk.document_version_id)
        .join(Source, Source.id == Document.source_id)
        .where(
            Chunk.id.in_([hit.chunk_id for hit in hits]),
            Chunk.tenant_id == scope.tenant_id,
            Document.tenant_id == scope.tenant_id,
            Source.tenant_id == scope.tenant_id,
            Document.allowed_principals.overlap(list(scope.principals)),
        )
    ).all()
    found = {
        chunk.id: (chunk, version, document, source) for chunk, version, document, source in rows
    }
    return [_passage(*found[hit.chunk_id], hit.score) for hit in hits if hit.chunk_id in found]


def _passage(
    chunk: Chunk, version: DocumentVersion, document: Document, source: Source, score: float
) -> Passage:
    return Passage(
        chunk_id=chunk.id,
        content=chunk.content,
        score=score,
        document_id=document.id,
        document_path=document.path,
        source_name=source.name,
        source_type=source.type,
        source_config=dict(source.config),
        heading_path=tuple(chunk.heading_path),
        start_line=chunk.start_line,
        end_line=chunk.end_line,
        page_start=chunk.page_start,
        page_end=chunk.page_end,
        revision=version.revision,
    )
