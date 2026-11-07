"""Initial schema, default tenant and default upload source

Revision ID: 0001
Revises:
Create Date: 2026-11-07
"""

from collections.abc import Sequence
from uuid import UUID

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Frozen copies of app.db.constants, so this migration never changes after it ships.
DEFAULT_TENANT_ID = UUID("00000000-0000-4000-8000-000000000001")
DEFAULT_UPLOAD_SOURCE_ID = UUID("00000000-0000-4000-8000-000000000002")
OPEN_JOB_CONDITION = "status IN ('pending', 'running', 'awaiting_embedding')"


def tenant_id_column(table: str) -> sa.Column:
    return sa.Column(
        "tenant_id",
        sa.Uuid(),
        sa.ForeignKey("tenants.id", name=f"fk_{table}_tenant_id_tenants"),
        nullable=False,
    )


def created_at_column() -> sa.Column:
    return sa.Column(
        "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )


def upgrade() -> None:
    op.create_table(
        "tenants",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_tenants"),
    )
    op.create_table(
        "sources",
        sa.Column("id", sa.Uuid(), nullable=False),
        tenant_id_column("sources"),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column(
            "config",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_sources"),
    )
    op.create_table(
        "documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        tenant_id_column("documents"),
        sa.Column(
            "source_id",
            sa.Uuid(),
            sa.ForeignKey("sources.id", name="fk_documents_source_id_sources"),
            nullable=False,
        ),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("file_type", sa.Text(), nullable=False),
        sa.Column(
            "allowed_principals",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{tenant}'"),
            nullable=False,
        ),
        sa.Column("current_version_id", sa.Uuid(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_documents"),
        sa.UniqueConstraint(
            "tenant_id", "source_id", "path", name="uq_documents_tenant_id_source_id_path"
        ),
    )
    op.create_table(
        "document_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        tenant_id_column("document_versions"),
        sa.Column(
            "document_id",
            sa.Uuid(),
            sa.ForeignKey("documents.id", name="fk_document_versions_document_id_documents"),
            nullable=False,
        ),
        sa.Column("content_hash", sa.Text(), nullable=False),
        sa.Column("revision", sa.Text(), nullable=True),
        sa.Column("storage_key", sa.Text(), nullable=False),
        created_at_column(),
        sa.PrimaryKeyConstraint("id", name="pk_document_versions"),
        sa.UniqueConstraint(
            "document_id", "content_hash", name="uq_document_versions_document_id_content_hash"
        ),
    )
    # documents and document_versions reference each other, so this key comes last.
    op.create_foreign_key(
        "fk_documents_current_version_id_document_versions",
        "documents",
        "document_versions",
        ["current_version_id"],
        ["id"],
    )
    op.create_table(
        "chunks",
        sa.Column("id", sa.Uuid(), nullable=False),
        tenant_id_column("chunks"),
        sa.Column(
            "document_version_id",
            sa.Uuid(),
            sa.ForeignKey(
                "document_versions.id", name="fk_chunks_document_version_id_document_versions"
            ),
            nullable=False,
        ),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "heading_path",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.Column("start_line", sa.Integer(), nullable=True),
        sa.Column("end_line", sa.Integer(), nullable=True),
        sa.Column("page_start", sa.Integer(), nullable=True),
        sa.Column("page_end", sa.Integer(), nullable=True),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("embedding_model", sa.Text(), nullable=True),
        sa.Column("embedded_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_chunks"),
        sa.UniqueConstraint(
            "document_version_id", "position", name="uq_chunks_document_version_id_position"
        ),
    )
    op.create_table(
        "ingestion_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        tenant_id_column("ingestion_jobs"),
        sa.Column(
            "source_id",
            sa.Uuid(),
            sa.ForeignKey("sources.id", name="fk_ingestion_jobs_source_id_sources"),
            nullable=False,
        ),
        sa.Column("status", sa.Text(), server_default=sa.text("'pending'"), nullable=False),
        sa.Column(
            "input", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False
        ),
        sa.Column(
            "file_counts",
            postgresql.JSONB(),
            server_default=sa.text("""'{"processed": 0, "skipped": 0, "failed": 0}'::jsonb"""),
            nullable=False,
        ),
        sa.Column(
            "errors", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        created_at_column(),
        sa.PrimaryKeyConstraint("id", name="pk_ingestion_jobs"),
    )
    op.create_index(
        "uq_ingestion_jobs_open_source_id",
        "ingestion_jobs",
        ["source_id"],
        unique=True,
        postgresql_where=sa.text(OPEN_JOB_CONDITION),
    )
    op.create_table(
        "query_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        tenant_id_column("query_logs"),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=True),
        sa.Column("outcome", sa.Text(), nullable=False),
        sa.Column(
            "chunk_ids",
            postgresql.ARRAY(sa.Uuid()),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.Column("model", sa.Text(), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        created_at_column(),
        sa.PrimaryKeyConstraint("id", name="pk_query_logs"),
    )

    tenants = sa.table("tenants", sa.column("id", sa.Uuid()), sa.column("name", sa.Text()))
    sources = sa.table(
        "sources",
        sa.column("id", sa.Uuid()),
        sa.column("tenant_id", sa.Uuid()),
        sa.column("type", sa.Text()),
        sa.column("name", sa.Text()),
    )
    op.bulk_insert(tenants, [{"id": DEFAULT_TENANT_ID, "name": "Default"}])
    op.bulk_insert(
        sources,
        [
            {
                "id": DEFAULT_UPLOAD_SOURCE_ID,
                "tenant_id": DEFAULT_TENANT_ID,
                "type": "upload",
                "name": "Uploads",
            }
        ],
    )


def downgrade() -> None:
    op.drop_table("query_logs")
    op.drop_index("uq_ingestion_jobs_open_source_id", table_name="ingestion_jobs")
    op.drop_table("ingestion_jobs")
    op.drop_table("chunks")
    op.drop_constraint(
        "fk_documents_current_version_id_document_versions", "documents", type_="foreignkey"
    )
    op.drop_table("document_versions")
    op.drop_table("documents")
    op.drop_table("sources")
    op.drop_table("tenants")
