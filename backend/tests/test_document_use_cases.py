from unittest.mock import AsyncMock

import pytest

from app.application.documents.ports import DocumentRecord, StoredUpload
from app.application.documents.use_cases import (
    DemoUploadForbiddenError,
    DocumentAlreadyProcessedError,
    DocumentNotFoundError,
    DocumentQueueUnavailableError,
    ProcessDocumentCommand,
    ProcessDocumentUseCase,
    ProcessQueueUnavailableError,
    UploadDocumentCommand,
    UploadDocumentUseCase,
)
from app.models.base import DocumentStatus


class DummyUploadFile:
    filename = "test.pdf"
    content_type = "application/pdf"
    size = 123

    async def read(self, size: int = -1) -> bytes:
        return b""


def _document_record(*, status: DocumentStatus) -> DocumentRecord:
    return DocumentRecord(
        id=1,
        user_id=11,
        filename="test.pdf",
        file_size=123,
        status=status,
        error_message=None,
        processed_at=None,
    )


@pytest.mark.asyncio
async def test_upload_use_case_rejects_demo_user_before_storage_call():
    storage = AsyncMock()
    documents = AsyncMock()
    queue = AsyncMock()
    use_case = UploadDocumentUseCase(storage=storage, documents=documents, queue=queue)

    with pytest.raises(DemoUploadForbiddenError):
        await use_case.execute(
            UploadDocumentCommand(
                user_id=11,
                user_is_demo=True,
                upload_file=DummyUploadFile(),
            )
        )

    storage.validate_and_store.assert_not_awaited()
    documents.create_pending_document.assert_not_awaited()
    queue.enqueue_document_processing.assert_not_awaited()


@pytest.mark.asyncio
async def test_upload_use_case_creates_document_and_queues_processing():
    storage = AsyncMock()
    documents = AsyncMock()
    queue = AsyncMock()
    storage.validate_and_store.return_value = StoredUpload(
        filename="test.pdf",
        file_path="uploads/test.pdf",
        file_size=123,
    )
    documents.create_pending_document.return_value = _document_record(
        status=DocumentStatus.PENDING
    )
    queue.enqueue_document_processing.return_value = True
    use_case = UploadDocumentUseCase(storage=storage, documents=documents, queue=queue)

    result = await use_case.execute(
        UploadDocumentCommand(
            user_id=11,
            user_is_demo=False,
            upload_file=DummyUploadFile(),
        )
    )

    assert result.id == 1
    assert result.status == DocumentStatus.PENDING
    queue.enqueue_document_processing.assert_awaited_once_with(document_id=1)


@pytest.mark.asyncio
async def test_upload_use_case_marks_document_failed_when_enqueue_raises():
    storage = AsyncMock()
    documents = AsyncMock()
    queue = AsyncMock()
    storage.validate_and_store.return_value = StoredUpload(
        filename="test.pdf",
        file_path="uploads/test.pdf",
        file_size=123,
    )
    documents.create_pending_document.return_value = _document_record(
        status=DocumentStatus.PENDING
    )
    queue.enqueue_document_processing.side_effect = RuntimeError("queue unavailable")
    use_case = UploadDocumentUseCase(storage=storage, documents=documents, queue=queue)

    with pytest.raises(DocumentQueueUnavailableError):
        await use_case.execute(
            UploadDocumentCommand(
                user_id=11,
                user_is_demo=False,
                upload_file=DummyUploadFile(),
            )
        )

    documents.mark_upload_queue_failed.assert_awaited_once_with(document_id=1)


@pytest.mark.asyncio
async def test_process_use_case_raises_not_found_for_missing_document():
    documents = AsyncMock()
    queue = AsyncMock()
    documents.get_user_document.return_value = None
    use_case = ProcessDocumentUseCase(documents=documents, queue=queue)

    with pytest.raises(DocumentNotFoundError):
        await use_case.execute(ProcessDocumentCommand(document_id=10, user_id=11))

    queue.enqueue_document_processing.assert_not_awaited()


@pytest.mark.asyncio
async def test_process_use_case_raises_already_processed_error():
    documents = AsyncMock()
    queue = AsyncMock()
    documents.get_user_document.return_value = _document_record(
        status=DocumentStatus.COMPLETED
    )
    use_case = ProcessDocumentUseCase(documents=documents, queue=queue)

    with pytest.raises(DocumentAlreadyProcessedError):
        await use_case.execute(ProcessDocumentCommand(document_id=10, user_id=11))

    queue.enqueue_document_processing.assert_not_awaited()


@pytest.mark.asyncio
async def test_process_use_case_resets_failed_then_marks_failed_on_queue_error():
    documents = AsyncMock()
    queue = AsyncMock()
    documents.get_user_document.return_value = _document_record(
        status=DocumentStatus.FAILED
    )
    queue.enqueue_document_processing.side_effect = RuntimeError("queue unavailable")
    use_case = ProcessDocumentUseCase(documents=documents, queue=queue)

    with pytest.raises(ProcessQueueUnavailableError):
        await use_case.execute(ProcessDocumentCommand(document_id=10, user_id=11))

    documents.reset_failed_document_for_retry.assert_awaited_once_with(document_id=1)
    documents.mark_process_queue_failed.assert_awaited_once_with(document_id=1)
