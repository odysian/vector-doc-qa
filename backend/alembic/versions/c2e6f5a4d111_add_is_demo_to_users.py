"""add is_demo to users

Revision ID: c2e6f5a4d111
Revises: a3c9b4f9d2e1
Create Date: 2026-03-04 15:55:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c2e6f5a4d111"
down_revision: Union[str, Sequence[str], None] = "a3c9b4f9d2e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "users",
        sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        schema="quaero",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("users", "is_demo", schema="quaero")
