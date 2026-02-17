"""add_refresh_tokens_table

Revision ID: f84628967c60
Revises: 49b4e1e72658
Create Date: 2026-02-17 14:20:33.020136

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f84628967c60"
down_revision: Union[str, Sequence[str], None] = "49b4e1e72658"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token", sa.String(length=255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["quaero.users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        schema="quaero",
    )
    op.create_index(
        "ix_quaero_refresh_tokens_id", "refresh_tokens", ["id"], unique=False, schema="quaero"
    )
    op.create_index(
        "ix_quaero_refresh_tokens_token", "refresh_tokens", ["token"], unique=True, schema="quaero"
    )
    op.create_index(
        "ix_quaero_refresh_tokens_user_id",
        "refresh_tokens",
        ["user_id"],
        unique=False,
        schema="quaero",
    )


def downgrade() -> None:
    op.drop_index("ix_quaero_refresh_tokens_user_id", table_name="refresh_tokens", schema="quaero")
    op.drop_index("ix_quaero_refresh_tokens_token", table_name="refresh_tokens", schema="quaero")
    op.drop_index("ix_quaero_refresh_tokens_id", table_name="refresh_tokens", schema="quaero")
    op.drop_table("refresh_tokens", schema="quaero")
