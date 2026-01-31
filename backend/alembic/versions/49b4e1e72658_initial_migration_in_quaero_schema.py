"""Initial migration in quaero schema

Revision ID: 49b4e1e72658
Revises:
Create Date: 2026-01-31 12:31:12.381184

"""

from typing import Sequence, Union

import pgvector.sqlalchemy
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "49b4e1e72658"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # pgvector must exist before creating chunks.embedding column.
    # Supabase has it available but it must be enabled (run before app/migrations).
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(length=50), nullable=False),
        sa.Column("email", sa.String(length=100), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        schema="quaero",
    )
    op.create_index(
        op.f("ix_quaero_users_email"), "users", ["email"], unique=True, schema="quaero"
    )
    op.create_index(
        op.f("ix_quaero_users_id"), "users", ["id"], unique=False, schema="quaero"
    )
    op.create_index(
        op.f("ix_quaero_users_username"),
        "users",
        ["username"],
        unique=True,
        schema="quaero",
    )
    op.create_table(
        "documents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("file_path", sa.String(length=500), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "PENDING", "PROCESSING", "COMPLETED", "FAILED", name="documentstatus"
            ),
            nullable=False,
        ),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(), nullable=False),
        sa.Column("processed_at", sa.DateTime(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["quaero.users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        schema="quaero",
    )
    op.create_index(
        op.f("ix_quaero_documents_id"),
        "documents",
        ["id"],
        unique=False,
        schema="quaero",
    )
    op.create_index(
        op.f("ix_quaero_documents_status"),
        "documents",
        ["status"],
        unique=False,
        schema="quaero",
    )
    op.create_index(
        op.f("ix_quaero_documents_user_id"),
        "documents",
        ["user_id"],
        unique=False,
        schema="quaero",
    )
    op.create_table(
        "chunks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column(
            "embedding", pgvector.sqlalchemy.vector.VECTOR(dim=1536), nullable=True
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["quaero.documents.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        schema="quaero",
    )
    op.create_index(
        op.f("ix_quaero_chunks_document_id"),
        "chunks",
        ["document_id"],
        unique=False,
        schema="quaero",
    )
    op.create_index(
        op.f("ix_quaero_chunks_id"), "chunks", ["id"], unique=False, schema="quaero"
    )
    op.create_table(
        "messages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("sources", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.CheckConstraint("role IN ('user', 'assistant')", name="check_role"),
        sa.ForeignKeyConstraint(
            ["document_id"], ["quaero.documents.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["quaero.users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        schema="quaero",
    )
    op.create_index(
        op.f("ix_quaero_messages_id"), "messages", ["id"], unique=False, schema="quaero"
    )


def downgrade() -> None:
    """Downgrade schema: drop quaero tables only (do not touch Supabase/Rostra)."""
    op.drop_index(op.f("ix_quaero_messages_id"), table_name="messages", schema="quaero")
    op.drop_table("messages", schema="quaero")
    op.drop_index(op.f("ix_quaero_chunks_id"), table_name="chunks", schema="quaero")
    op.drop_index(
        op.f("ix_quaero_chunks_document_id"), table_name="chunks", schema="quaero"
    )
    op.drop_table("chunks", schema="quaero")
    op.drop_index(
        op.f("ix_quaero_documents_user_id"), table_name="documents", schema="quaero"
    )
    op.drop_index(
        op.f("ix_quaero_documents_status"), table_name="documents", schema="quaero"
    )
    op.drop_index(
        op.f("ix_quaero_documents_id"), table_name="documents", schema="quaero"
    )
    op.drop_table("documents", schema="quaero")
    op.drop_index(op.f("ix_quaero_users_username"), table_name="users", schema="quaero")
    op.drop_index(op.f("ix_quaero_users_id"), table_name="users", schema="quaero")
    op.drop_index(op.f("ix_quaero_users_email"), table_name="users", schema="quaero")
    op.drop_table("users", schema="quaero")
