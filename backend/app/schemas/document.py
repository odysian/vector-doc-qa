from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from app.models.base import DocumentStatus


class DocumentResponse(BaseModel):
    """Response model for a document."""

    id: int
    user_id: int
    filename: str
    file_size: int
    status: DocumentStatus
    uploaded_at: datetime
    processed_at: Optional[datetime] = None
    error_message: Optional[str] = None

    class Config:
        from_attributes = True


class DocumentListResponse(BaseModel):
    """Response model for list of documents."""

    documents: list[DocumentResponse]
    total: int


class UploadResponse(BaseModel):
    """Response immediately after file upload."""

    id: int
    user_id: int
    filename: str
    file_size: int
    status: DocumentStatus
    message: str = "File uploaded successfully"


class DocumentStatusResponse(BaseModel):
    """Lightweight response model for polling document processing status."""

    id: int
    status: DocumentStatus
    processed_at: Optional[datetime] = None
    error_message: Optional[str] = None
