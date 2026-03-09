"""add workspace schema and message context constraint

Revision ID: b3f7c1a2e4d5
Revises: d4f7a9c1e2b3
Create Date: 2026-03-09 03:20:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b3f7c1a2e4d5"
down_revision: Union[str, Sequence[str], None] = "d4f7a9c1e2b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "workspaces",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["quaero.users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.Index("ix_quaero_workspaces_user_id", "user_id"),
        sa.Index("ix_quaero_workspaces_id", "id"),
        schema="quaero",
    )

    op.create_table(
        "workspace_documents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column(
            "added_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["quaero.workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["quaero.documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workspace_id", "document_id", name="uq_workspace_documents_workspace_document"
        ),
        sa.Index("ix_quaero_workspace_documents_id", "id"),
        sa.Index("ix_quaero_workspace_documents_workspace_id", "workspace_id"),
        sa.Index("ix_quaero_workspace_documents_document_id", "document_id"),
        schema="quaero",
    )

    op.add_column(
        "messages",
        sa.Column(
            "workspace_id",
            sa.Integer(),
            sa.ForeignKey("quaero.workspaces.id", ondelete="CASCADE"),
            nullable=True,
        ),
        schema="quaero",
    )

    op.alter_column(
        "messages",
        "document_id",
        existing_type=sa.Integer(),
        nullable=True,
        schema="quaero",
    )

    op.create_check_constraint(
        "check_message_context",
        "messages",
        "(document_id IS NOT NULL AND workspace_id IS NULL) OR "
        "(document_id IS NULL AND workspace_id IS NOT NULL)",
        schema="quaero",
    )

    op.create_index(
        "ix_quaero_messages_workspace_id",
        "messages",
        ["workspace_id"],
        schema="quaero",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_quaero_messages_workspace_id", table_name="messages", schema="quaero")
    op.drop_constraint("check_message_context", "messages", schema="quaero", type_="check")
    op.alter_column(
        "messages",
        "document_id",
        existing_type=sa.Integer(),
        nullable=False,
        schema="quaero",
    )
    op.drop_column("messages", "workspace_id", schema="quaero")

    op.drop_index(
        "ix_quaero_workspace_documents_document_id",
        table_name="workspace_documents",
        schema="quaero",
    )
    op.drop_index(
        "ix_quaero_workspace_documents_workspace_id",
        table_name="workspace_documents",
        schema="quaero",
    )
    op.drop_table("workspace_documents", schema="quaero")
    op.drop_table("workspaces", schema="quaero")
