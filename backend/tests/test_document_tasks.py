from unittest.mock import AsyncMock, patch


class _DummyAsyncSessionContext:
    def __init__(self, session: object):
        self.session = session

    async def __aenter__(self) -> object:
        return self.session

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None


class TestDocumentWorkerTask:
    async def test_process_document_task_calls_service(self):
        from app.workers.document_tasks import process_document_task

        fake_session = object()
        with (
            patch(
                "app.workers.document_tasks.AsyncSessionLocal",
                return_value=_DummyAsyncSessionContext(fake_session),
            ),
            patch(
                "app.workers.document_tasks.process_document_text",
                new=AsyncMock(return_value=None),
            ) as mock_process,
        ):
            await process_document_task({}, 42)

        mock_process.assert_awaited_once_with(document_id=42, db=fake_session)

    async def test_process_document_task_swallows_value_error(self):
        from app.workers.document_tasks import process_document_task

        with (
            patch(
                "app.workers.document_tasks.AsyncSessionLocal",
                return_value=_DummyAsyncSessionContext(object()),
            ),
            patch(
                "app.workers.document_tasks.process_document_text",
                new=AsyncMock(side_effect=ValueError("already completed")),
            ),
        ):
            await process_document_task({}, 42)

    async def test_process_document_task_swallows_unexpected_exception(self):
        from app.workers.document_tasks import process_document_task

        with (
            patch(
                "app.workers.document_tasks.AsyncSessionLocal",
                return_value=_DummyAsyncSessionContext(object()),
            ),
            patch(
                "app.workers.document_tasks.process_document_text",
                new=AsyncMock(side_effect=RuntimeError("boom")),
            ),
        ):
            await process_document_task({}, 42)
