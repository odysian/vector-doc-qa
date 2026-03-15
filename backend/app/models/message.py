from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from app.database import Base
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from app.models.base import Document
    from app.models.workspace import Workspace
    from app.models.user import User


class Message(Base):
    """Represents a chat message in a document Q&A conversation."""

    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=True
    )
    workspace_id: Mapped[int | None] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=True, index=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    sources: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True
    )  # Only for assistant messages
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    # Relationships
    document: Mapped["Document | None"] = relationship(back_populates="messages")  # type: ignore
    user: Mapped["User"] = relationship(back_populates="messages")  # type: ignore
    workspace: Mapped["Workspace | None"] = relationship(back_populates="messages")  # type: ignore

    # Constraint to ensure role is either 'user' or 'assistant'
    __table_args__ = (
        CheckConstraint("role IN ('user', 'assistant')", name="check_role"),
        CheckConstraint(
            "(document_id IS NOT NULL AND workspace_id IS NULL) OR "
            "(document_id IS NULL AND workspace_id IS NOT NULL)",
            name="check_message_context",
        ),
        Index(
            "ix_quaero_messages_document_id_user_id_created_at_id",
            document_id,
            user_id,
            created_at.desc(),
            id.desc(),
        ),
        # Standalone index on user_id to accelerate CASCADE delete scans.
        Index("ix_quaero_messages_user_id", user_id),
    )

    def __repr__(self) -> str:
        return f"<Message(id={self.id}, role='{self.role}', document_id={self.document_id})>"
