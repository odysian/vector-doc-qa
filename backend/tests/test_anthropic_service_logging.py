from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.anthropic_service import (
    _build_prompt,
    generate_answer,
    generate_answer_stream,
)


class _FakeStreamContext:
    def __init__(self, tokens: list[str]):
        self._tokens = tokens

    async def __aenter__(self) -> SimpleNamespace:
        async def _token_stream():
            for token in self._tokens:
                yield token

        return SimpleNamespace(text_stream=_token_stream())

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
