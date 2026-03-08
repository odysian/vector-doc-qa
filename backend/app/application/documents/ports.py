from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.models.base import DocumentStatus


class UploadFileLike(Protocol):
    """Transport-agnostic subset needed for upload validation/storage."""

    filename: str | None
    content_type: str | None
    size: int | None

    async def read(self, size: int = -1) -> bytes: ...


@dataclass(slots=True)
class StoredUpload:
    filename: str
    file_path: str
    file_size: int


@dataclass(slots=True)
class DocumentRecord:
    id: int
    user_id: int
    filename: str
    file_size: int
    status: DocumentStatus
    error_message: str | None
    processed_at: datetime | None


class UploadStoragePort(Protocol):
    async def validate_and_store(self, upload_file: UploadFileLike) -> StoredUpload: ...


class DocumentCommandPort(Protocol):
    async def create_pending_document(
        self,
        *,
        user_id: int,
        filename: str,
        file_path: str,
        file_size: int,
    ) -> DocumentRecord: ...

    async def get_user_document(
        self,
        *,
        document_id: int,
        user_id: int,
    ) -> DocumentRecord | None: ...

    async def reset_failed_document_for_retry(self, *, document_id: int) -> None: ...

    async def mark_upload_queue_failed(self, *, document_id: int) -> None: ...

    async def mark_process_queue_failed(self, *, document_id: int) -> None: ...


class DocumentProcessingQueuePort(Protocol):
    async def enqueue_document_processing(self, *, document_id: int) -> bool: ...
