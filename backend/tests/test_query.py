"""
Tests for search, query (RAG), and chat history endpoints.

Covers TESTPLAN.md "Feature: Document Search", "Document Query (RAG)",
and "Chat History".
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.message import Message
from app.models.user import User


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
