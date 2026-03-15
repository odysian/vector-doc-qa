"""add messages user_id index

Revision ID: e1a2b3c4d5e6
Revises: 4e6a1ee7ab3c
Create Date: 2026-03-14 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e1a2b3c4d5e6"
down_revision: Union[str, Sequence[str], None] = "4e6a1ee7ab3c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

INDEX_NAME = "ix_quaero_messages_user_id"


def upgrade() -> None:
    """Add standalone index on messages.user_id to support CASCADE delete scans."""
    op.execute(
        f"CREATE INDEX IF NOT EXISTS {INDEX_NAME} ON quaero.messages (user_id)"
    )


def downgrade() -> None:
    """Remove messages.user_id index."""
    op.drop_index(INDEX_NAME, table_name="messages", schema="quaero")
