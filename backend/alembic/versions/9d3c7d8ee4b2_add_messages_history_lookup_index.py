"""add messages history lookup index

Revision ID: 9d3c7d8ee4b2
Revises: c2e6f5a4d111
Create Date: 2026-03-05 23:40:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9d3c7d8ee4b2"
down_revision: Union[str, Sequence[str], None] = "c2e6f5a4d111"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

INDEX_NAME = "ix_quaero_messages_document_id_user_id_created_at_id"


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        "CREATE INDEX IF NOT EXISTS "
        f"{INDEX_NAME} "
        "ON quaero.messages (document_id, user_id, created_at DESC, id DESC)"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(INDEX_NAME, table_name="messages", schema="quaero")
