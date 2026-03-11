from unittest.mock import AsyncMock, patch

import pytest

from app.services.queue_service import enqueue_document_processing


class TestQueueServiceEvents:
    async def test_emits_queue_enqueued_event(self) -> None:
        fake_pool = AsyncMock()
        fake_pool.enqueue_job = AsyncMock(return_value=object())

        with (
            patch(
                "app.services.queue_service._get_queue_pool",
                new=AsyncMock(return_value=fake_pool),
            ),
            patch("app.services.queue_service.logger.info") as mock_info,
        ):
            was_enqueued = await enqueue_document_processing(42)

        assert was_enqueued is True
        matching_calls = [
            call
            for call in mock_info.call_args_list
            if call.args and call.args[0] == "document.queue_enqueued"
        ]
        assert len(matching_calls) == 1
        assert matching_calls[0].kwargs["extra"]["document_id"] == 42

    async def test_emits_queue_duplicate_event(self) -> None:
        fake_pool = AsyncMock()
        fake_pool.enqueue_job = AsyncMock(return_value=None)

        with (
            patch(
                "app.services.queue_service._get_queue_pool",
                new=AsyncMock(return_value=fake_pool),
            ),
            patch("app.services.queue_service.logger.info") as mock_info,
        ):
            was_enqueued = await enqueue_document_processing(84)

        assert was_enqueued is False
        matching_calls = [
            call
            for call in mock_info.call_args_list
            if call.args and call.args[0] == "document.queue_duplicate"
        ]
        assert len(matching_calls) == 1
        assert matching_calls[0].kwargs["extra"]["document_id"] == 84

    async def test_emits_queue_failed_event_on_enqueue_error(self) -> None:
        with (
            patch(
                "app.services.queue_service._get_queue_pool",
                new=AsyncMock(side_effect=RuntimeError("redis unavailable")),
            ),
            patch("app.services.queue_service.logger.error") as mock_error,
        ):
            with pytest.raises(RuntimeError, match="redis unavailable"):
                await enqueue_document_processing(21)

        assert mock_error.call_count == 1
        error_call = mock_error.call_args
        assert error_call is not None
        assert error_call.args[0] == "document.queue_failed"
        assert error_call.kwargs["extra"]["document_id"] == 21
        assert error_call.kwargs["exc_info"] is True
