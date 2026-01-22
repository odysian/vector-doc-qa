"""
SQLAlchemy database models with SQLAlchemy 2.0 type annotations.

Uses Mapped[] for proper type checking support.
"""

import enum
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class DocumentStatus(str, enum.Enum):
    """Document processing status."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Document(Base):
    """
    Represents a single uploaded PDF file.

    Stores metadata about the file, not the actual content.
    The PDF file lives on disk in the uploads/ directory.
    """

    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    filename: Mapped[str] = mapped_column(String(255))
    file_path: Mapped[str] = mapped_column(String(500))
    file_size: Mapped[int]

    status: Mapped[DocumentStatus] = mapped_column(
        SQLEnum(DocumentStatus), default=DocumentStatus.PENDING, index=True
    )

    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    processed_at: Mapped[datetime | None] = mapped_column(DateTime, default=None)

    error_message: Mapped[str | None] = mapped_column(Text, default=None)

    # RELATIONSHIPS
    chunks: Mapped[list["Chunk"]] = relationship(
        back_populates="document", cascade="all, delete-orphan", lazy="select"
    )

    def __repr__(self) -> str:
        return f"<Document(id={self.id}, filename='{self.filename}', status='{self.status.value}')>"


class Chunk(Base):
    """
    Represents a piece of text extracted from a document.

    Each chunk has its own vector embedding for semantic search.
    """

    __tablename__ = "chunks"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), index=True)
    content: Mapped[str] = mapped_column(Text)
    chunk_index: Mapped[int]

    # Vector embedding (nullable - added after chunk creation)
    embedding: Mapped[Vector | None] = mapped_column(Vector(1536), default=None)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    document: Mapped["Document"] = relationship(back_populates="chunks")

    def __repr__(self) -> str:
        return f"<Chunk(id={self.id}, document_id={self.document_id}, index={self.chunk_index})>"
