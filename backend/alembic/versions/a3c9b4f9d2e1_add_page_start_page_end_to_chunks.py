"""add page_start page_end to chunks

Revision ID: a3c9b4f9d2e1
Revises: f84628967c60
Create Date: 2026-03-03 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a3c9b4f9d2e1"
down_revision: Union[str, Sequence[str], None] = "f84628967c60"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "chunks",
        sa.Column("page_start", sa.Integer(), nullable=True),
        schema="quaero",
    )
    op.add_column(
        "chunks",
        sa.Column("page_end", sa.Integer(), nullable=True),
        schema="quaero",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("chunks", "page_end", schema="quaero")
    op.drop_column("chunks", "page_start", schema="quaero")
