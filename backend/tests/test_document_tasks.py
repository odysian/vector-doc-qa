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
            patch("app.workers.document_tasks.logger.info") as mock_info,
        ):
            await process_document_task({"job_id": "job-42"}, 42)

        mock_process.assert_awaited_once_with(document_id=42, db=fake_session)
        event_messages = [call.args[0] for call in mock_info.call_args_list if call.args]
        assert "worker.job_started" in event_messages
        assert "worker.job_completed" in event_messages

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
            patch("app.workers.document_tasks.logger.warning") as mock_warning,
        ):
            await process_document_task({}, 42)

        warning_messages = [
            call.args[0] for call in mock_warning.call_args_list if call.args
        ]
        assert "worker.job_failed" in warning_messages

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
            patch("app.workers.document_tasks.logger.exception") as mock_exception,
        ):
            await process_document_task({}, 42)

        exception_messages = [
            call.args[0] for call in mock_exception.call_args_list if call.args
        ]
        assert "worker.job_failed" in exception_messages
