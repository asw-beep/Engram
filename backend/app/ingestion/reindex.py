"""Rebuild the keyword index from PostgreSQL, which stays canonical (spec section 4).

It writes every chunk of every current version, for every tenant, each under its own tenant
and permissions. Run on an emptied index it restores exactly what PostgreSQL holds; run on a
live one it adds what is missing and rewrites what drifted. It never removes entries. One
left behind when removing an old version failed stays until the index is emptied and
rebuilt, because a later publish removes only the version that was current then; search
rechecks the current version in PostgreSQL, so such an entry is never shown.
"""

from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.db.keyword_index import (
    IndexedText,
    KeywordIndex,
    heading_text,
    is_transient_opensearch_error,
)
from app.db.models import Chunk, Document
from app.retrying import retry_transient


def reindex_keyword(
    session: Session, keyword_index: KeywordIndex, batch_size: int = 500, retry_wait: float = 1.0
) -> int:
    """Upsert every current version's chunks in batches by chunk ID. Returns the count."""
    keyword_index.ensure_index()
    count = 0
    after: UUID | None = None
    while True:
        query = (
            select(
                Chunk.id,
                Chunk.content,
                Chunk.heading_path,
                Chunk.tenant_id,
                Chunk.document_version_id,
                Document.id.label("document_id"),
                Document.allowed_principals,
            )
            .join(
                Document,
                and_(
                    Document.current_version_id == Chunk.document_version_id,
                    Document.tenant_id == Chunk.tenant_id,
                ),
            )
            .order_by(Chunk.id)
            .limit(batch_size)
        )
        if after is not None:
            query = query.where(Chunk.id > after)
        rows = session.execute(query).all()
        if not rows:
            return count
        texts = [
            IndexedText(
                chunk_id=row.id,
                content=row.content,
                headings=heading_text(row.heading_path),
                tenant_id=row.tenant_id,
                document_id=row.document_id,
                document_version_id=row.document_version_id,
                allowed_principals=list(row.allowed_principals),
            )
            for row in rows
        ]
        retry_transient(
            lambda texts=texts: keyword_index.upsert(texts),
            is_transient_opensearch_error,
            wait_base=retry_wait,
        )
        count += len(rows)
        after = rows[-1].id
