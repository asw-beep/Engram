"""Record which deferred job each waiting document version belongs to

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("document_versions", sa.Column("awaiting_job_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_document_versions_awaiting_job_id_ingestion_jobs",
        "document_versions",
        "ingestion_jobs",
        ["awaiting_job_id"],
        ["id"],
    )
    op.create_index(
        "ix_document_versions_awaiting_job_id", "document_versions", ["awaiting_job_id"]
    )
    # Jobs already waiting had no record of their versions: give each one the versions with
    # unembedded chunks in its source, which is what export would have used before.
    op.execute(
        """
        UPDATE document_versions AS v
        SET awaiting_job_id = j.id
        FROM documents AS d, ingestion_jobs AS j
        WHERE v.document_id = d.id
          AND d.source_id = j.source_id
          AND j.status = 'awaiting_embedding'
          AND EXISTS (
            SELECT 1 FROM chunks AS c
            WHERE c.document_version_id = v.id AND c.embedded_at IS NULL
          )
        """
    )


def downgrade() -> None:
    op.drop_index("ix_document_versions_awaiting_job_id", table_name="document_versions")
    op.drop_constraint(
        "fk_document_versions_awaiting_job_id_ingestion_jobs",
        "document_versions",
        type_="foreignkey",
    )
    op.drop_column("document_versions", "awaiting_job_id")
