from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.constants import EMBEDDING_DIMENSIONS, EMBEDDING_MODEL
from app.services import embedding_service
from app.services.embedding_service import (
    consume_last_embedding_usage_tokens,
    generate_embeddings_batch,
)


@pytest.fixture(autouse=True)
def reset_embedding_client_singleton():
    embedding_service._client = None
    yield
    embedding_service._client = None


class TestGenerateEmbeddingsBatch:
    async def test_fails_fast_when_batch_contains_empty_text(self):
        with patch("app.services.embedding_service.AsyncOpenAI") as mock_client:
            with pytest.raises(
                ValueError,
                match="Invalid batch text at index 1: must be a non-empty string",
            ):
                await generate_embeddings_batch(["first chunk", "   "])

        mock_client.assert_not_called()

    async def test_returns_embeddings_in_input_order_using_response_indexes(self):
        response = SimpleNamespace(
            data=[
                SimpleNamespace(index=1, embedding=[0.2] * EMBEDDING_DIMENSIONS),
                SimpleNamespace(index=0, embedding=[0.1] * EMBEDDING_DIMENSIONS),
            ]
        )
        create_mock = AsyncMock(return_value=response)

        with patch("app.services.embedding_service.AsyncOpenAI") as mock_client:
            mock_client.return_value.embeddings.create = create_mock

            embeddings = await generate_embeddings_batch(["chunk-0", "chunk-1"])

        create_mock.assert_awaited_once_with(
            model=EMBEDDING_MODEL,
            input=["chunk-0", "chunk-1"],
            encoding_format="float",
        )
        assert embeddings[0] == [0.1] * EMBEDDING_DIMENSIONS
        assert embeddings[1] == [0.2] * EMBEDDING_DIMENSIONS

    async def test_raises_when_embedding_count_does_not_match_input_count(self):
        response = SimpleNamespace(
            data=[SimpleNamespace(index=0, embedding=[0.1] * EMBEDDING_DIMENSIONS)]
        )
        create_mock = AsyncMock(return_value=response)

        with patch("app.services.embedding_service.AsyncOpenAI") as mock_client:
            mock_client.return_value.embeddings.create = create_mock

            with pytest.raises(ValueError, match="Expected 2 embeddings, got 1"):
                await generate_embeddings_batch(["chunk-0", "chunk-1"])

    async def test_records_embedding_usage_tokens_for_callers(self):
        response = SimpleNamespace(
            usage=SimpleNamespace(prompt_tokens=42),
            data=[SimpleNamespace(index=0, embedding=[0.1] * EMBEDDING_DIMENSIONS)],
        )
        create_mock = AsyncMock(return_value=response)

        with patch("app.services.embedding_service.AsyncOpenAI") as mock_client:
            mock_client.return_value.embeddings.create = create_mock
            await generate_embeddings_batch(["chunk-0"])

        assert consume_last_embedding_usage_tokens() == 42
        assert consume_last_embedding_usage_tokens() is None

    async def test_emits_external_call_completed_with_embedding_tokens(self):
        response = SimpleNamespace(
            usage=SimpleNamespace(prompt_tokens=11),
            data=[SimpleNamespace(index=0, embedding=[0.1] * EMBEDDING_DIMENSIONS)],
        )
        create_mock = AsyncMock(return_value=response)

        with (
            patch("app.services.embedding_service.AsyncOpenAI") as mock_client,
            patch("app.services.embedding_service.logger.info") as mock_info,
        ):
            mock_client.return_value.embeddings.create = create_mock
            await generate_embeddings_batch(["chunk-0"])

        completion_calls = [
            call
            for call in mock_info.call_args_list
            if call.args and call.args[0] == "external.call_completed"
        ]
        assert len(completion_calls) == 1
        completion_extra = completion_calls[0].kwargs["extra"]
        assert completion_extra["provider"] == "openai"
        assert completion_extra["model"] == EMBEDDING_MODEL
        assert completion_extra["embedding_tokens"] == 11
