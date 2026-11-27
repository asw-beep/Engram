"""Record each question's retrieval mode and stage timings in the query log

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Rows written before this revision keep nulls: their mode and timings weren't recorded.
COLUMNS = (
    ("retrieval_mode", sa.Text()),
    ("reranked", sa.Boolean()),
    ("retrieve_ms", sa.Integer()),
    ("rerank_ms", sa.Integer()),
    ("generate_ms", sa.Integer()),
)


def upgrade() -> None:
    for name, kind in COLUMNS:
        op.add_column("query_logs", sa.Column(name, kind, nullable=True))


def downgrade() -> None:
    for name, _ in reversed(COLUMNS):
        op.drop_column("query_logs", name)
