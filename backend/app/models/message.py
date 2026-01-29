from __future__ import annotations

from datetime import datetime

from app.database import Base
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship


class Message(Base):
    """Represents a chat message in a document Q&A conversation."""

    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
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
    document: Mapped["Document"] = relationship(back_populates="messages")  # type: ignore
    user: Mapped["User"] = relationship(back_populates="messages")  # type: ignore

    # Constraint to ensure role is either 'user' or 'assistant'
    __table_args__ = (
        CheckConstraint("role IN ('user', 'assistant')", name="check_role"),
    )

    def __repr__(self) -> str:
        return f"<Message(id={self.id}, role='{self.role}', document_id={self.document_id})>"
