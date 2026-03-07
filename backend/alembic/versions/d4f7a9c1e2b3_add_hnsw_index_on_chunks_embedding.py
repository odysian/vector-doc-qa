"""add hnsw index on chunks embedding

Revision ID: d4f7a9c1e2b3
Revises: 9d3c7d8ee4b2
Create Date: 2026-03-06 21:34:39.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4f7a9c1e2b3"
down_revision: Union[str, Sequence[str], None] = "9d3c7d8ee4b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

INDEX_NAME = "ix_quaero_chunks_embedding_hnsw"


def upgrade() -> None:
    """Upgrade schema."""
    # Some local/dev pgvector builds may not expose hnsw + vector_cosine_ops yet.
    # Keep migration chain forward-compatible by no-oping with a NOTICE in that case.
    op.execute(
        "DO $$ "
        "BEGIN "
        "BEGIN "
        "EXECUTE 'CREATE INDEX IF NOT EXISTS "
        f"{INDEX_NAME} "
        "ON quaero.chunks "
        "USING hnsw (embedding vector_cosine_ops) "
        "WHERE embedding IS NOT NULL'; "
        "EXCEPTION "
        "WHEN undefined_object THEN "
        f"RAISE NOTICE '{INDEX_NAME} skipped: hnsw vector_cosine_ops unavailable'; "
        "END; "
        "END $$"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(f"DROP INDEX IF EXISTS quaero.{INDEX_NAME}")
