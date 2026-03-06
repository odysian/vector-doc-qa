"""
Tests for search, query (RAG), and chat history endpoints.

Covers TESTPLAN.md "Feature: Document Search", "Document Query (RAG)",
and "Chat History".
"""

import json
from collections.abc import AsyncGenerator
from unittest.mock import patch

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import documents as documents_api
from app.models.message import Message
from app.models.user import User


class _NoCloseSessionContext:
    """Async context manager that reuses fixture session without closing it."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def __aenter__(self) -> AsyncSession:
        return self.session

    async def __aexit__(self, exc_type, exc, tb) -> bool:  # type: ignore[no-untyped-def]
        return False


class _FailingWriteSession:
    """Minimal async session double that fails on commit."""

    def add(self, _obj) -> None:  # type: ignore[no-untyped-def]
        return None

    async def commit(self) -> None:
        raise RuntimeError("write failed")

    async def refresh(self, _obj) -> None:  # type: ignore[no-untyped-def]
        return None


class _FailingSessionContext:
    """Async context manager returning a failing write session."""

    def __init__(self):
        self.session = _FailingWriteSession()

    async def __aenter__(self) -> _FailingWriteSession:
        return self.session

    async def __aexit__(self, exc_type, exc, tb) -> bool:  # type: ignore[no-untyped-def]
        return False


async def _read_sse_events(response) -> list[tuple[str, str]]:  # type: ignore[no-untyped-def]
    """Collect SSE events until a terminal done/error event is reached."""
    events: list[tuple[str, str]] = []
    event_name: str | None = None
    data_lines: list[str] = []

    async for line in response.aiter_lines():
        if line == "":
            if event_name is not None:
                data = "\n".join(data_lines)
                events.append((event_name, data))
                if event_name in {"done", "error"}:
                    break
            event_name = None
            data_lines = []
            continue

        if line.startswith("event:"):
            event_name = line[6:].strip()
            continue

        if line.startswith("data:"):
            data = line[5:]
            if data.startswith(" "):
                data = data[1:]
            data_lines.append(data)

    return events


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


class TestSearch:
    """POST /api/documents/{id}/search"""

    async def test_search_returns_ranked_results(
        self, client, auth_headers, processed_document, mock_embeddings
    ):
        response = await client.post(
            f"/api/documents/{processed_document.id}/search",
            headers=auth_headers,
            json={"query": "test query", "top_k": 3},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["query"] == "test query"
        assert data["document_id"] == processed_document.id
        assert len(data["results"]) <= 3
        assert data["total_results"] == len(data["results"])

        # Each result should have the expected shape
        for result in data["results"]:
            assert "chunk_id" in result
            assert "content" in result
            assert "similarity" in result
            assert "chunk_index" in result
            assert "page_start" in result
            assert "page_end" in result

    async def test_search_returns_404_for_other_users_document(
        self, client, second_user_headers, processed_document
    ):
        response = await client.post(
            f"/api/documents/{processed_document.id}/search",
            headers=second_user_headers,
            json={"query": "test query"},
        )
        assert response.status_code == 404

    async def test_search_info_logs_redact_raw_query(
        self, client, auth_headers, processed_document, mock_embeddings
    ):
        raw_query = "salary details for q4"
        with patch("app.services.search_service.logger.info") as mock_info:
            response = await client.post(
                f"/api/documents/{processed_document.id}/search",
                headers=auth_headers,
                json={"query": raw_query, "top_k": 3},
            )

        assert response.status_code == 200
        info_messages = [call.args[0] for call in mock_info.call_args_list]
        assert any("query_chars=" in message for message in info_messages)
        assert all(raw_query not in message for message in info_messages)

    async def test_search_error_log_uses_structured_context(
        self,
        client,
        auth_headers,
        processed_document,
        test_user: User,
    ):
        with (
            patch(
                "app.api.documents.search_chunks",
                side_effect=RuntimeError("sensitive search payload"),
            ),
            patch("app.api.documents.logger.error") as mock_error,
        ):
            response = await client.post(
                f"/api/documents/{processed_document.id}/search",
                headers=auth_headers,
                json={"query": "how much?"},
            )

        assert response.status_code == 500
        assert response.json()["detail"] == "Search failed"
        assert mock_error.call_count == 1
        error_call = mock_error.call_args
        assert error_call is not None
        assert error_call.args == (
            "Search failed for document_id=%s, user_id=%s, error_class=%s",
            processed_document.id,
            test_user.id,
            "RuntimeError",
        )
        assert error_call.kwargs["exc_info"] is True
        assert "sensitive search payload" not in str(error_call)


# ---------------------------------------------------------------------------
# Query (RAG)
# ---------------------------------------------------------------------------


class TestQuery:
    """POST /api/documents/{id}/query"""

    async def test_query_returns_answer_with_sources(
        self, client, auth_headers, processed_document, mock_embeddings, mock_anthropic
    ):
        response = await client.post(
            f"/api/documents/{processed_document.id}/query",
            headers=auth_headers,
            json={"query": "What is this document about?"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["query"] == "What is this document about?"
        assert len(data["answer"]) > 0
        assert "sources" in data
        assert isinstance(data["sources"], list)
        assert "pipeline_meta" in data
        assert data["pipeline_meta"]["chunks_retrieved"] == len(data["sources"])

    async def test_query_saves_user_and_assistant_messages(
        self,
        client,
        auth_headers,
        processed_document,
        mock_embeddings,
        mock_anthropic,
        db_session: AsyncSession,
        test_user: User,
    ):
        await client.post(
            f"/api/documents/{processed_document.id}/query",
            headers=auth_headers,
            json={"query": "Tell me about the content"},
        )

        # Check that both user and assistant messages were saved
        result = await db_session.execute(
            select(Message)
            .where(Message.document_id == processed_document.id)
            .where(Message.user_id == test_user.id)
            .order_by(Message.created_at)
        )
        messages = result.scalars().all()

        assert len(messages) == 2
        assert messages[0].role == "user"
        assert messages[0].content == "Tell me about the content"
        assert messages[1].role == "assistant"
        assert len(messages[1].content) > 0
        # Assistant message should have sources stored as JSONB
        assert messages[1].sources is not None

    async def test_query_passes_bounded_ordered_history_to_prompt(
        self,
        client,
        auth_headers,
        processed_document,
        mock_embeddings,
        mock_anthropic,
        db_session: AsyncSession,
        test_user: User,
    ):
        turn_count = documents_api.CONVERSATION_HISTORY_WINDOW_TURNS + 1
        expected_history: list[dict[str, str]] = []

        for turn in range(turn_count):
            user_content = f"user turn {turn}"
            assistant_content = f"assistant turn {turn}"
            db_session.add(
                Message(
                    document_id=processed_document.id,
                    user_id=test_user.id,
                    role="user",
                    content=user_content,
                )
            )
            db_session.add(
                Message(
                    document_id=processed_document.id,
                    user_id=test_user.id,
                    role="assistant",
                    content=assistant_content,
                )
            )
            if turn > 0:
                expected_history.extend(
                    [
                        {"role": "user", "content": user_content},
                        {"role": "assistant", "content": assistant_content},
                    ]
                )

        await db_session.flush()

        response = await client.post(
            f"/api/documents/{processed_document.id}/query",
            headers=auth_headers,
            json={"query": "Follow up question"},
        )

        assert response.status_code == 200
        assert mock_anthropic["api"].await_count == 1
        call_kwargs = mock_anthropic["api"].await_args.kwargs
        assert call_kwargs["query"] == "Follow up question"
        assert call_kwargs["conversation_history"] == expected_history

    async def test_query_returns_404_for_other_users_document(
        self, client, second_user_headers, processed_document, mock_embeddings, mock_anthropic
    ):
        response = await client.post(
            f"/api/documents/{processed_document.id}/query",
            headers=second_user_headers,
            json={"query": "test"},
        )
        assert response.status_code == 404

    async def test_query_info_logs_redact_raw_query(
        self,
        client,
        auth_headers,
        processed_document,
        mock_embeddings,
        mock_anthropic,
        test_user: User,
    ):
        raw_query = "sensitive compensation details"
        with patch("app.api.documents.logger.info") as mock_info:
            response = await client.post(
                f"/api/documents/{processed_document.id}/query",
                headers=auth_headers,
                json={"query": raw_query},
            )

        assert response.status_code == 200
        info_messages = [call.args[0] for call in mock_info.call_args_list]
        assert any(
            f"user_id={test_user.id}" in message and "query_chars=" in message
            for message in info_messages
        )
        assert all(raw_query not in message for message in info_messages)

    async def test_query_error_log_uses_structured_context(
        self,
        client,
        auth_headers,
        processed_document,
        test_user: User,
    ):
        with (
            patch(
                "app.api.documents.generate_embedding",
                side_effect=RuntimeError("sensitive query payload"),
            ),
            patch("app.api.documents.logger.error") as mock_error,
        ):
            response = await client.post(
                f"/api/documents/{processed_document.id}/query",
                headers=auth_headers,
                json={"query": "where is the budget?"},
            )

        assert response.status_code == 500
        assert response.json()["detail"] == "Query failed"
        assert mock_error.call_count == 1
        error_call = mock_error.call_args
        assert error_call is not None
        assert error_call.args == (
            "Query failed for document_id=%s, user_id=%s, error_class=%s",
            processed_document.id,
            test_user.id,
            "RuntimeError",
        )
        assert error_call.kwargs["exc_info"] is True
        assert "sensitive query payload" not in str(error_call)


# ---------------------------------------------------------------------------
# Query Stream (SSE)
# ---------------------------------------------------------------------------


class TestQueryStream:
    """POST /api/documents/{id}/query/stream"""

    async def test_stream_query_returns_expected_sse_events(
        self,
        client,
        auth_headers,
        processed_document,
        mock_embeddings,
        db_session: AsyncSession,
    ):
        async def _fake_generate_answer_stream(
            query: str,
            chunks: list[dict],
            conversation_history: list[dict[str, str]] | None = None,
        ) -> AsyncGenerator[str, None]:
            del query, chunks, conversation_history
            yield "This "
            yield "is "
            yield "streamed."

        with (
            patch(
                "app.api.documents.generate_answer_stream",
                new=_fake_generate_answer_stream,
            ),
            patch(
                "app.api.documents.AsyncSessionLocal",
                new=lambda: _NoCloseSessionContext(db_session),
            ),
        ):
            async with client.stream(
                "POST",
                f"/api/documents/{processed_document.id}/query/stream",
                headers=auth_headers,
                json={"query": "Summarize this document"},
            ) as response:
                assert response.status_code == 200
                assert response.headers["content-type"].startswith("text/event-stream")
                events = await _read_sse_events(response)

        event_types = [event for event, _ in events]
        assert event_types == ["sources", "token", "token", "token", "meta", "done"]

        sources_payload = json.loads(events[0][1])
        assert isinstance(sources_payload, list)
        assert len(sources_payload) > 0
        assert "similarity" in sources_payload[0]

        token_payloads = [payload for event, payload in events if event == "token"]
        assert "".join(token_payloads) == "This is streamed."

        meta_payload = json.loads(events[4][1])
        assert set(meta_payload.keys()) == {
            "embed_ms",
            "retrieval_ms",
            "llm_ms",
            "total_ms",
            "top_similarity",
            "avg_similarity",
            "chunks_retrieved",
        }

        done_payload = json.loads(events[5][1])
        assert isinstance(done_payload["message_id"], int)

    async def test_stream_query_returns_404_for_other_users_document(
        self, client, second_user_headers, processed_document
    ):
        response = await client.post(
            f"/api/documents/{processed_document.id}/query/stream",
            headers=second_user_headers,
            json={"query": "test"},
        )
        assert response.status_code == 404

    async def test_stream_query_returns_400_for_unprocessed_document(
        self, client, auth_headers, test_document
    ):
        response = await client.post(
            f"/api/documents/{test_document.id}/query/stream",
            headers=auth_headers,
            json={"query": "test"},
        )
        assert response.status_code == 400

    async def test_stream_query_info_logs_redact_raw_query(
        self,
        client,
        auth_headers,
        processed_document,
        mock_embeddings,
        db_session: AsyncSession,
        test_user: User,
    ):
        raw_query = "tell me internal budget notes"

        async def _fake_generate_answer_stream(
            query: str,
            chunks: list[dict],
            conversation_history: list[dict[str, str]] | None = None,
        ) -> AsyncGenerator[str, None]:
            del query, chunks, conversation_history
            yield "streamed answer"

        with (
            patch("app.api.documents.logger.info") as mock_info,
            patch(
                "app.api.documents.generate_answer_stream",
                new=_fake_generate_answer_stream,
            ),
            patch(
                "app.api.documents.AsyncSessionLocal",
                new=lambda: _NoCloseSessionContext(db_session),
            ),
        ):
            async with client.stream(
                "POST",
                f"/api/documents/{processed_document.id}/query/stream",
                headers=auth_headers,
                json={"query": raw_query},
            ) as response:
                assert response.status_code == 200
                await _read_sse_events(response)

        info_messages = [call.args[0] for call in mock_info.call_args_list]
        assert any(
            f"user_id={test_user.id}" in message and "query_chars=" in message
            for message in info_messages
        )
        assert all(raw_query not in message for message in info_messages)

    async def test_stream_query_setup_error_log_uses_structured_context(
        self,
        client,
        auth_headers,
        processed_document,
        test_user: User,
    ):
        with (
            patch(
                "app.api.documents.generate_embedding",
                side_effect=RuntimeError("sensitive stream setup payload"),
            ),
            patch("app.api.documents.logger.error") as mock_error,
        ):
            response = await client.post(
                f"/api/documents/{processed_document.id}/query/stream",
                headers=auth_headers,
                json={"query": "summarize"},
            )

        assert response.status_code == 500
        assert response.json()["detail"] == "Query failed"
        assert mock_error.call_count == 1
        error_call = mock_error.call_args
        assert error_call is not None
        assert error_call.args == (
            "Streaming query setup failed for document_id=%s, user_id=%s, error_class=%s",
            processed_document.id,
            test_user.id,
            "RuntimeError",
        )
        assert error_call.kwargs["exc_info"] is True
        assert "sensitive stream setup payload" not in str(error_call)

    async def test_stream_query_emits_error_event_when_llm_stream_fails(
        self,
        client,
        auth_headers,
        processed_document,
        mock_embeddings,
        db_session: AsyncSession,
        test_user: User,
    ):
        async def _failing_generate_answer_stream(
            query: str,
            chunks: list[dict],
            conversation_history: list[dict[str, str]] | None = None,
        ) -> AsyncGenerator[str, None]:
            del query, chunks, conversation_history
            yield "partial "
            raise RuntimeError("anthropic stream failed")

        with patch(
            "app.api.documents.generate_answer_stream",
            new=_failing_generate_answer_stream,
        ), patch(
            "app.api.documents.AsyncSessionLocal",
            new=lambda: _NoCloseSessionContext(db_session),
        ):
            async with client.stream(
                "POST",
                f"/api/documents/{processed_document.id}/query/stream",
                headers=auth_headers,
                json={"query": "Summarize this document"},
            ) as response:
                assert response.status_code == 200
                events = await _read_sse_events(response)

        event_types = [event for event, _ in events]
        assert event_types == ["sources", "token", "error"]
        assert json.loads(events[-1][1]) == {"detail": "Query failed"}

        result = await db_session.execute(
            select(Message)
            .where(Message.document_id == processed_document.id)
            .where(Message.user_id == test_user.id)
            .order_by(Message.created_at)
        )
        messages = result.scalars().all()
        assert len(messages) == 2
        assert messages[0].role == "user"
        assert messages[1].role == "assistant"
        assert "partial" in messages[1].content.lower()

    async def test_stream_query_runtime_error_log_uses_structured_context(
        self,
        client,
        auth_headers,
        processed_document,
        mock_embeddings,
        db_session: AsyncSession,
        test_user: User,
    ):
        async def _failing_generate_answer_stream(
            query: str,
            chunks: list[dict],
            conversation_history: list[dict[str, str]] | None = None,
        ) -> AsyncGenerator[str, None]:
            del query, chunks, conversation_history
            yield "partial "
            raise RuntimeError("sensitive stream runtime payload")

        with (
            patch(
                "app.api.documents.generate_answer_stream",
                new=_failing_generate_answer_stream,
            ),
            patch(
                "app.api.documents.AsyncSessionLocal",
                new=lambda: _NoCloseSessionContext(db_session),
            ),
            patch("app.api.documents.logger.error") as mock_error,
        ):
            async with client.stream(
                "POST",
                f"/api/documents/{processed_document.id}/query/stream",
                headers=auth_headers,
                json={"query": "Summarize this document"},
            ) as response:
                assert response.status_code == 200
                events = await _read_sse_events(response)

        event_types = [event for event, _ in events]
        assert event_types == ["sources", "token", "error"]
        assert json.loads(events[-1][1]) == {"detail": "Query failed"}

        matching_calls = [
            call
            for call in mock_error.call_args_list
            if call.args
            and call.args[0]
            == "Streaming query failed for document_id=%s, user_id=%s, error_class=%s"
        ]
        assert len(matching_calls) == 1
        error_call = matching_calls[0]
        assert error_call.args[1:] == (
            processed_document.id,
            test_user.id,
            "RuntimeError",
        )
        assert error_call.kwargs["exc_info"] is True
        assert "sensitive stream runtime payload" not in str(error_call)

    async def test_stream_query_emits_error_event_when_db_save_fails(
        self,
        client,
        auth_headers,
        processed_document,
        mock_embeddings,
        db_session: AsyncSession,
        test_user: User,
    ):
        async def _fake_generate_answer_stream(
            query: str,
            chunks: list[dict],
            conversation_history: list[dict[str, str]] | None = None,
        ) -> AsyncGenerator[str, None]:
            del query, chunks, conversation_history
            yield "streamed token"

        fail_then_succeed_calls = {"count": 0}

        def _fail_then_succeed_session():
            fail_then_succeed_calls["count"] += 1
            if fail_then_succeed_calls["count"] == 1:
                return _FailingSessionContext()
            return _NoCloseSessionContext(db_session)

        with (
            patch(
                "app.api.documents.generate_answer_stream",
                new=_fake_generate_answer_stream,
            ),
            patch(
                "app.api.documents.AsyncSessionLocal",
                new=_fail_then_succeed_session,
            ),
        ):
            async with client.stream(
                "POST",
                f"/api/documents/{processed_document.id}/query/stream",
                headers=auth_headers,
                json={"query": "Summarize this document"},
            ) as response:
                assert response.status_code == 200
                events = await _read_sse_events(response)

        event_types = [event for event, _ in events]
        assert event_types == ["sources", "token", "meta", "error"]
        assert json.loads(events[-1][1]) == {"detail": "Query failed"}

        result = await db_session.execute(
            select(Message)
            .where(Message.document_id == processed_document.id)
            .where(Message.user_id == test_user.id)
            .order_by(Message.created_at)
        )
        messages = result.scalars().all()
        assert len(messages) == 2
        assert messages[0].role == "user"
        assert messages[1].role == "assistant"
        assert "internal error saving the final response" in messages[1].content.lower()

    async def test_stream_query_passes_bounded_ordered_history_to_prompt(
        self,
        client,
        auth_headers,
        processed_document,
        mock_embeddings,
        db_session: AsyncSession,
        test_user: User,
    ):
        turn_count = documents_api.CONVERSATION_HISTORY_WINDOW_TURNS + 1
        expected_history: list[dict[str, str]] = []

        for turn in range(turn_count):
            user_content = f"user turn {turn}"
            assistant_content = f"assistant turn {turn}"
            db_session.add(
                Message(
                    document_id=processed_document.id,
                    user_id=test_user.id,
                    role="user",
                    content=user_content,
                )
            )
            db_session.add(
                Message(
                    document_id=processed_document.id,
                    user_id=test_user.id,
                    role="assistant",
                    content=assistant_content,
                )
            )
            if turn > 0:
                expected_history.extend(
                    [
                        {"role": "user", "content": user_content},
                        {"role": "assistant", "content": assistant_content},
                    ]
                )

        await db_session.flush()

        observed_history: dict[str, list[dict[str, str]]] = {"messages": []}

        async def _fake_generate_answer_stream(
            query: str,
            chunks: list[dict],
            conversation_history: list[dict[str, str]] | None = None,
        ) -> AsyncGenerator[str, None]:
            del query, chunks
            observed_history["messages"] = conversation_history or []
            yield "streamed answer"

        with (
            patch(
                "app.api.documents.generate_answer_stream",
                new=_fake_generate_answer_stream,
            ),
            patch(
                "app.api.documents.AsyncSessionLocal",
                new=lambda: _NoCloseSessionContext(db_session),
            ),
        ):
            async with client.stream(
                "POST",
                f"/api/documents/{processed_document.id}/query/stream",
                headers=auth_headers,
                json={"query": "Follow up stream question"},
            ) as response:
                assert response.status_code == 200
                await _read_sse_events(response)

        assert observed_history["messages"] == expected_history


# ---------------------------------------------------------------------------
# Messages (Chat History)
# ---------------------------------------------------------------------------


class TestMessages:
    """GET /api/documents/{id}/messages"""

    async def test_get_messages_returns_chat_history(
        self,
        client,
        auth_headers,
        processed_document,
        db_session: AsyncSession,
        test_user: User,
    ):
        # Create some messages directly in the DB
        user_msg = Message(
            document_id=processed_document.id,
            user_id=test_user.id,
            role="user",
            content="What is this?",
        )
        asst_msg = Message(
            document_id=processed_document.id,
            user_id=test_user.id,
            role="assistant",
            content="This is a test document.",
            sources=[{"chunk_id": 1, "content": "test", "similarity": 0.9, "chunk_index": 0}],
        )
        db_session.add(user_msg)
        db_session.add(asst_msg)
        await db_session.flush()

        response = await client.get(
            f"/api/documents/{processed_document.id}/messages",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert data["messages"][0]["role"] == "user"
        assert data["messages"][1]["role"] == "assistant"
        assert data["messages"][1]["sources"] is not None

    async def test_get_messages_returns_empty_for_no_messages(
        self, client, auth_headers, processed_document
    ):
        response = await client.get(
            f"/api/documents/{processed_document.id}/messages",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["messages"] == []

    async def test_get_messages_returns_404_for_other_users_document(
        self, client, second_user_headers, processed_document
    ):
        response = await client.get(
            f"/api/documents/{processed_document.id}/messages",
            headers=second_user_headers,
        )
        assert response.status_code == 404
