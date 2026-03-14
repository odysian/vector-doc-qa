"""fix_timezone_naive_datetime_columns

Revision ID: 4e6a1ee7ab3c
Revises: b3f7c1a2e4d5
Create Date: 2026-03-14 19:19:32.672607

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "4e6a1ee7ab3c"
down_revision: Union[str, Sequence[str], None] = "b3f7c1a2e4d5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Convert timezone-naive datetime columns to TIMESTAMPTZ and add server defaults."""
    # documents.uploaded_at: naive -> tz-aware, add server default
    op.alter_column(
        "documents",
        "uploaded_at",
        type_=sa.DateTime(timezone=True),
        postgresql_using="uploaded_at AT TIME ZONE 'UTC'",
        server_default=sa.text("now()"),
        schema="quaero",
    )
    # documents.processed_at: naive -> tz-aware (stays nullable, no server default)
    op.alter_column(
        "documents",
        "processed_at",
        type_=sa.DateTime(timezone=True),
        postgresql_using="processed_at AT TIME ZONE 'UTC'",
        schema="quaero",
    )
    # chunks.created_at: naive -> tz-aware, add server default
    op.alter_column(
        "chunks",
        "created_at",
        type_=sa.DateTime(timezone=True),
        postgresql_using="created_at AT TIME ZONE 'UTC'",
        server_default=sa.text("now()"),
        schema="quaero",
    )


def downgrade() -> None:
    """Revert TIMESTAMPTZ columns back to naive TIMESTAMP and drop server defaults."""
    # documents.uploaded_at: tz-aware -> naive, drop server default
    op.alter_column(
        "documents",
        "uploaded_at",
        type_=sa.DateTime(timezone=False),
        postgresql_using="uploaded_at AT TIME ZONE 'UTC'",
        server_default=None,
        schema="quaero",
    )
    # documents.processed_at: tz-aware -> naive
    op.alter_column(
        "documents",
        "processed_at",
        type_=sa.DateTime(timezone=False),
        postgresql_using="processed_at AT TIME ZONE 'UTC'",
        schema="quaero",
    )
    # chunks.created_at: tz-aware -> naive, drop server default
    op.alter_column(
        "chunks",
        "created_at",
        type_=sa.DateTime(timezone=False),
        postgresql_using="created_at AT TIME ZONE 'UTC'",
        server_default=None,
        schema="quaero",
    )
