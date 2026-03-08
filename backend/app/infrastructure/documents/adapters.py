from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import cast

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.documents.ports import (
    DocumentRecord,
    StoredUpload,
    UploadFileLike,
)
from app.models.base import Document, DocumentStatus
from app.utils.file_utils import save_upload_file, validate_file_upload


class FileUtilsUploadStorageAdapter:
    async def validate_and_store(self, upload_file: UploadFileLike) -> StoredUpload:
        fastapi_upload = cast(UploadFile, upload_file)
        validate_file_upload(fastapi_upload)
        file_path, file_size = await save_upload_file(fastapi_upload)
        filename = fastapi_upload.filename or ""

        return StoredUpload(
            filename=filename,
            file_path=file_path,
            file_size=file_size,
        )


class SQLAlchemyDocumentCommandAdapter:
    def __init__(self, *, db: AsyncSession):
        self._db = db

    async def create_pending_document(
        self,
        *,
        user_id: int,
        filename: str,
        file_path: str,
        file_size: int,
    ) -> DocumentRecord:
        document = Document(
            filename=filename,
            file_path=file_path,
            file_size=file_size,
            status=DocumentStatus.PENDING,
            user_id=user_id,
        )
        self._db.add(document)
        await self._db.commit()
        await self._db.refresh(document)
        return _to_document_record(document)

    async def get_user_document(
        self,
        *,
        document_id: int,
        user_id: int,
    ) -> DocumentRecord | None:
        document = await self._db.scalar(
            select(Document)
            .where(Document.id == document_id)
            .where(Document.user_id == user_id)
        )
        if document is None:
            return None
        return _to_document_record(document)

    async def reset_failed_document_for_retry(self, *, document_id: int) -> None:
        document = await self._db.scalar(select(Document).where(Document.id == document_id))
        if document is None:
            return

        document.status = DocumentStatus.PENDING
        document.error_message = None
        document.processed_at = None
        await self._db.commit()

    async def mark_upload_queue_failed(self, *, document_id: int) -> None:
        document = await self._db.scalar(select(Document).where(Document.id == document_id))
        if document is None:
            return

        document.status = DocumentStatus.FAILED
        document.error_message = "Upload succeeded, but queueing failed. Please retry."
        await self._db.commit()

    async def mark_process_queue_failed(self, *, document_id: int) -> None:
        document = await self._db.scalar(select(Document).where(Document.id == document_id))
        if document is None:
            return

        document.status = DocumentStatus.FAILED
        document.error_message = "Queueing failed. Please retry processing."
        await self._db.commit()


class QueueServiceAdapter:
    def __init__(self, *, enqueue_document_processing_fn: Callable[[int], Awaitable[bool]]):
        self._enqueue_document_processing_fn = enqueue_document_processing_fn

    async def enqueue_document_processing(self, *, document_id: int) -> bool:
        return await self._enqueue_document_processing_fn(document_id)


def _to_document_record(document: Document) -> DocumentRecord:
    return DocumentRecord(
        id=document.id,
        user_id=document.user_id,
        filename=document.filename,
        file_size=document.file_size,
        status=document.status,
        error_message=document.error_message,
        processed_at=document.processed_at,
    )
