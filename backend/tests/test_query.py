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

    async def test_search_returns_404_for_other_users_document(
        self, client, second_user_headers, processed_document
    ):
        response = await client.post(
            f"/api/documents/{processed_document.id}/search",
            headers=second_user_headers,
            json={"query": "test query"},
        )
        assert response.status_code == 404


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

    async def test_query_returns_404_for_other_users_document(
        self, client, second_user_headers, processed_document, mock_embeddings, mock_anthropic
    ):
        response = await client.post(
            f"/api/documents/{processed_document.id}/query",
            headers=second_user_headers,
            json={"query": "test"},
        )
        assert response.status_code == 404


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
        ) -> AsyncGenerator[str, None]:
            del query, chunks
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

    async def test_stream_query_emits_error_event_when_llm_stream_fails(
        self, client, auth_headers, processed_document, mock_embeddings
    ):
        async def _failing_generate_answer_stream(
            query: str,
            chunks: list[dict],
        ) -> AsyncGenerator[str, None]:
            del query, chunks
            yield "partial "
            raise RuntimeError("anthropic stream failed")

        with patch(
            "app.api.documents.generate_answer_stream",
            new=_failing_generate_answer_stream,
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

    async def test_stream_query_emits_error_event_when_db_save_fails(
        self, client, auth_headers, processed_document, mock_embeddings
    ):
        async def _fake_generate_answer_stream(
            query: str,
            chunks: list[dict],
        ) -> AsyncGenerator[str, None]:
            del query, chunks
            yield "streamed token"

        with (
            patch(
                "app.api.documents.generate_answer_stream",
                new=_fake_generate_answer_stream,
            ),
            patch(
                "app.api.documents.AsyncSessionLocal",
                new=lambda: _FailingSessionContext(),
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
