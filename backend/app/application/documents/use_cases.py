from __future__ import annotations

from dataclasses import dataclass

from app.application.documents.ports import (
    DocumentCommandPort,
    DocumentProcessingQueuePort,
    UploadFileLike,
    UploadStoragePort,
)
from app.models.base import DocumentStatus


class DemoUploadForbiddenError(Exception):
    pass


class DocumentQueueUnavailableError(Exception):
    def __init__(self, *, document_id: int):
        super().__init__("Document could not be queued for processing.")
        self.document_id = document_id


class DocumentNotFoundError(Exception):
    pass


class DocumentAlreadyProcessedError(Exception):
    pass


class DocumentAlreadyProcessingError(Exception):
    pass


class ProcessQueueUnavailableError(Exception):
    def __init__(self, *, document_id: int):
        super().__init__("Failed to queue document processing.")
        self.document_id = document_id


@dataclass(slots=True)
class UploadDocumentCommand:
    user_id: int
    user_is_demo: bool
    upload_file: UploadFileLike


@dataclass(slots=True)
class UploadDocumentResult:
    id: int
    user_id: int
    filename: str
    file_size: int
    status: DocumentStatus
    message: str


class UploadDocumentUseCase:
    def __init__(
        self,
        *,
        storage: UploadStoragePort,
        documents: DocumentCommandPort,
        queue: DocumentProcessingQueuePort,
    ):
        self._storage = storage
        self._documents = documents
        self._queue = queue

    async def execute(self, command: UploadDocumentCommand) -> UploadDocumentResult:
        if command.user_is_demo:
            raise DemoUploadForbiddenError

        stored_upload = await self._storage.validate_and_store(command.upload_file)
        document = await self._documents.create_pending_document(
            user_id=command.user_id,
            filename=stored_upload.filename,
            file_path=stored_upload.file_path,
            file_size=stored_upload.file_size,
        )

        try:
            await self._queue.enqueue_document_processing(document_id=document.id)
        except Exception as exc:
            await self._documents.mark_upload_queue_failed(document_id=document.id)
            raise DocumentQueueUnavailableError(document_id=document.id) from exc

        return UploadDocumentResult(
            id=document.id,
            user_id=document.user_id,
            filename=document.filename,
            file_size=document.file_size,
            status=document.status,
            message="File uploaded successfully. Processing started in background.",
        )


@dataclass(slots=True)
class ProcessDocumentCommand:
    document_id: int
    user_id: int


@dataclass(slots=True)
class ProcessDocumentResult:
    document_id: int
    message: str


class ProcessDocumentUseCase:
    def __init__(
        self,
        *,
        documents: DocumentCommandPort,
        queue: DocumentProcessingQueuePort,
    ):
        self._documents = documents
        self._queue = queue

    async def execute(self, command: ProcessDocumentCommand) -> ProcessDocumentResult:
        document = await self._documents.get_user_document(
            document_id=command.document_id,
            user_id=command.user_id,
        )
        if document is None:
            raise DocumentNotFoundError

        if document.status == DocumentStatus.COMPLETED:
            raise DocumentAlreadyProcessedError

        if document.status == DocumentStatus.PROCESSING:
            raise DocumentAlreadyProcessingError

        if document.status == DocumentStatus.FAILED:
            await self._documents.reset_failed_document_for_retry(document_id=document.id)

        try:
            enqueued = await self._queue.enqueue_document_processing(document_id=document.id)
        except Exception as exc:
            await self._documents.mark_process_queue_failed(document_id=document.id)
            raise ProcessQueueUnavailableError(document_id=document.id) from exc

        message = (
            f"Document {document.id} processing already queued"
            if not enqueued
            else f"Document {document.id} queued for background processing"
        )
        return ProcessDocumentResult(
            document_id=document.id,
            message=message,
        )
