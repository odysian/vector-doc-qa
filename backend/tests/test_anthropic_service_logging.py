from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.anthropic_service import (
    _build_prompt,
    consume_last_answer_usage,
    consume_last_stream_usage,
    generate_answer,
    generate_answer_stream,
)


class _FakeStreamContext:
    def __init__(
        self,
        tokens: list[str],
        *,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
    ):
        self._tokens = tokens
        self._input_tokens = input_tokens
        self._output_tokens = output_tokens

    async def __aenter__(self) -> SimpleNamespace:
        async def _token_stream():
            for token in self._tokens:
                yield token

        async def _get_final_message() -> SimpleNamespace:
            return SimpleNamespace(
                usage=SimpleNamespace(
                    input_tokens=self._input_tokens,
                    output_tokens=self._output_tokens,
                    cache_creation_input_tokens=None,
                    cache_read_input_tokens=None,
                )
            )

        return SimpleNamespace(
            text_stream=_token_stream(),
            get_final_message=_get_final_message,
        )

    async def __aexit__(self, exc_type, exc, tb) -> bool:  # type: ignore[no-untyped-def]
        return False


class _FailingFinalMessageStreamContext:
    def __init__(self, tokens: list[str]):
        self._tokens = tokens

    async def __aenter__(self) -> SimpleNamespace:
        async def _token_stream():
            for token in self._tokens:
                yield token

        async def _get_final_message() -> SimpleNamespace:
            raise RuntimeError("final usage unavailable")

        return SimpleNamespace(
            text_stream=_token_stream(),
            get_final_message=_get_final_message,
        )

    async def __aexit__(self, exc_type, exc, tb) -> bool:  # type: ignore[no-untyped-def]
        return False


class TestAnthropicServiceLogging:
    def test_build_prompt_formats_history_with_explicit_roles(self):
        prompt = _build_prompt(
            query="What changed?",
            chunks=[{"content": "Excerpt content"}],
            conversation_history=[
                {"role": "user", "content": "Summarize section 1"},
                {"role": "assistant", "content": "Section 1 is about costs"},
            ],
        )

        assert "Recent conversation history (oldest to newest):" in prompt
        assert "User: Summarize section 1" in prompt
        assert "Assistant: Section 1 is about costs" in prompt
        assert "Current question: What changed?" in prompt

    def test_build_prompt_includes_document_filenames_for_workspace_chunks(self):
        prompt = _build_prompt(
            query="What changed?",
            chunks=[
                {"content": "Revenue increased.", "document_filename": "q1.pdf"},
                {"content": "Expenses decreased.", "document_filename": "q2.pdf"},
            ],
        )

        assert "Here are excerpts from multiple documents:" in prompt
        assert 'Excerpt 1 (from "q1.pdf"):' in prompt
        assert 'Excerpt 2 (from "q2.pdf"):' in prompt
        assert "mention which document it came from" in prompt

    async def test_generate_answer_info_logs_redact_raw_query(self):
        raw_query = "board compensation details"
        chunks = [{"content": "Compensation details are in this excerpt."}]
        response = SimpleNamespace(content=[SimpleNamespace(text="answer")])
        create_mock = AsyncMock(return_value=response)
        fake_client = SimpleNamespace(messages=SimpleNamespace(create=create_mock))

        with (
            patch("app.services.anthropic_service._get_client", return_value=fake_client),
            patch("app.services.anthropic_service.logger.info") as mock_info,
        ):
            answer = await generate_answer(query=raw_query, chunks=chunks)

        assert answer == "answer"
        info_messages = [call.args[0] for call in mock_info.call_args_list]
        assert any("query_chars=" in message for message in info_messages)
        assert all(raw_query not in message for message in info_messages)

    async def test_generate_answer_stream_info_logs_redact_raw_query(self):
        raw_query = "future merger timeline"
        chunks = [{"content": "Timeline details are in this excerpt."}]
        stream_mock = MagicMock(return_value=_FakeStreamContext(["first", " second"]))
        fake_client = SimpleNamespace(messages=SimpleNamespace(stream=stream_mock))

        with (
            patch("app.services.anthropic_service._get_client", return_value=fake_client),
            patch("app.services.anthropic_service.logger.info") as mock_info,
        ):
            tokens = [token async for token in generate_answer_stream(query=raw_query, chunks=chunks)]

        assert tokens == ["first", " second"]
        info_messages = [call.args[0] for call in mock_info.call_args_list]
        assert any("query_chars=" in message for message in info_messages)
        assert all(raw_query not in message for message in info_messages)

    async def test_generate_answer_stores_usage_for_callers(self):
        chunks = [{"content": "Compensation details are in this excerpt."}]
        response = SimpleNamespace(
            usage=SimpleNamespace(
                input_tokens=13,
                output_tokens=5,
                cache_creation_input_tokens=0,
                cache_read_input_tokens=0,
            ),
            content=[SimpleNamespace(text="answer")],
        )
        create_mock = AsyncMock(return_value=response)
        fake_client = SimpleNamespace(messages=SimpleNamespace(create=create_mock))

        with patch("app.services.anthropic_service._get_client", return_value=fake_client):
            answer = await generate_answer(query="summary?", chunks=chunks)

        usage = consume_last_answer_usage()
        assert answer == "answer"
        assert usage is not None
        assert usage.input_tokens == 13
        assert usage.output_tokens == 5

    async def test_generate_answer_stream_stores_final_usage_for_callers(self):
        chunks = [{"content": "Timeline details are in this excerpt."}]
        stream_mock = MagicMock(
            return_value=_FakeStreamContext(
                ["part 1", " part 2"],
                input_tokens=21,
                output_tokens=8,
            )
        )
        fake_client = SimpleNamespace(messages=SimpleNamespace(stream=stream_mock))

        with patch("app.services.anthropic_service._get_client", return_value=fake_client):
            tokens = [token async for token in generate_answer_stream(query="timeline?", chunks=chunks)]

        usage = consume_last_stream_usage()
        assert tokens == ["part 1", " part 2"]
        assert usage is not None
        assert usage.input_tokens == 21
        assert usage.output_tokens == 8

    async def test_generate_answer_stream_tolerates_final_usage_extraction_failure(self):
        chunks = [{"content": "Timeline details are in this excerpt."}]
        stream_mock = MagicMock(
            return_value=_FailingFinalMessageStreamContext(["part 1", " part 2"])
        )
        fake_client = SimpleNamespace(messages=SimpleNamespace(stream=stream_mock))

        with (
            patch("app.services.anthropic_service._get_client", return_value=fake_client),
            patch("app.services.anthropic_service.logger.warning") as mock_warning,
            patch("app.services.anthropic_service.logger.info") as mock_info,
        ):
            tokens = [token async for token in generate_answer_stream(query="timeline?", chunks=chunks)]

        usage = consume_last_stream_usage()
        assert tokens == ["part 1", " part 2"]
        assert usage is None

        warning_messages = [call.args[0] for call in mock_warning.call_args_list if call.args]
        assert "external.call_usage_unavailable" in warning_messages

        completion_calls = [
            call for call in mock_info.call_args_list if call.args and call.args[0] == "external.call_completed"
        ]
        assert len(completion_calls) == 1
