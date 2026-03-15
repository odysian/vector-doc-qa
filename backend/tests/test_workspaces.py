"""
Tests for workspace endpoints: CRUD, membership, query, and workspace chat history.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models.base import Chunk, Document, DocumentStatus
from app.models.message import Message
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceDocument

FAKE_EMBEDDING = [0.1] * 1536


def _auth_headers_for_user(user: User) -> dict[str, str]:
    token = create_access_token(data={"sub": str(user.id)})
    return {"Authorization": f"Bearer {token}"}


async def _create_completed_document(
    *,
    db_session: AsyncSession,
    user_id: int,
    filename: str,
) -> Document:
    document = Document(
        filename=filename,
        file_path=f"uploads/{filename}",
        file_size=2048,
        status=DocumentStatus.COMPLETED,
        user_id=user_id,
        processed_at=datetime.now(timezone.utc),
    )
    db_session.add(document)
    await db_session.flush()
    return document


class TestWorkspaceCrud:
    async def test_create_workspace_returns_201(self, client, auth_headers):
        response = await client.post(
            "/api/workspaces/",
            headers=auth_headers,
            json={"name": "Quarterly Reports"},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Quarterly Reports"
        assert data["document_count"] == 0
        assert "id" in data

    async def test_create_workspace_returns_403_for_demo_user(
        self,
        client,
        db_session: AsyncSession,
    ):
        demo_user = User(
            username="demo_workspace_user",
            email="demo_workspace_user@example.com",
            hashed_password="unused",
            is_demo=True,
        )
        db_session.add(demo_user)
        await db_session.flush()

        response = await client.post(
            "/api/workspaces/",
            headers=_auth_headers_for_user(demo_user),
            json={"name": "Demo workspace"},
        )

        assert response.status_code == 403
        assert response.json()["detail"] == "Demo account cannot create workspaces"

    async def test_list_workspaces_returns_only_owned_with_document_counts(
        self,
        client,
        auth_headers,
        test_user: User,
        second_user: User,
        db_session: AsyncSession,
    ):
        owned_workspace = Workspace(name="Owned", user_id=test_user.id)
        other_workspace = Workspace(name="Other", user_id=second_user.id)
        db_session.add_all([owned_workspace, other_workspace])
        await db_session.flush()

        owned_doc = await _create_completed_document(
            db_session=db_session,
            user_id=test_user.id,
            filename="owned.pdf",
        )
        db_session.add(
            WorkspaceDocument(
                workspace_id=owned_workspace.id,
                document_id=owned_doc.id,
            )
        )
        await db_session.flush()

        response = await client.get("/api/workspaces/", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["workspaces"][0]["id"] == owned_workspace.id
        assert data["workspaces"][0]["document_count"] == 1

    async def test_get_workspace_returns_documents_in_added_order(
        self,
        client,
        auth_headers,
        test_user: User,
        db_session: AsyncSession,
    ):
        workspace = Workspace(name="Research", user_id=test_user.id)
        db_session.add(workspace)
        await db_session.flush()

        doc_one = await _create_completed_document(
            db_session=db_session,
            user_id=test_user.id,
            filename="one.pdf",
        )
        doc_two = await _create_completed_document(
            db_session=db_session,
            user_id=test_user.id,
            filename="two.pdf",
        )
        db_session.add(WorkspaceDocument(workspace_id=workspace.id, document_id=doc_one.id))
        db_session.add(WorkspaceDocument(workspace_id=workspace.id, document_id=doc_two.id))
        await db_session.flush()

        response = await client.get(
            f"/api/workspaces/{workspace.id}",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert [doc["id"] for doc in data["documents"]] == [doc_one.id, doc_two.id]

    async def test_update_workspace_updates_name(
        self,
        client,
        auth_headers,
        test_user: User,
        db_session: AsyncSession,
    ):
        workspace = Workspace(name="Old Name", user_id=test_user.id)
        db_session.add(workspace)
        await db_session.flush()

        response = await client.patch(
            f"/api/workspaces/{workspace.id}",
            headers=auth_headers,
            json={"name": "New Name"},
        )

        assert response.status_code == 200
        assert response.json()["name"] == "New Name"

    async def test_delete_workspace_returns_404_for_other_user(
        self,
        client,
        second_user_headers,
        test_user: User,
        db_session: AsyncSession,
    ):
        workspace = Workspace(name="Private", user_id=test_user.id)
        db_session.add(workspace)
        await db_session.flush()

        response = await client.delete(
            f"/api/workspaces/{workspace.id}",
            headers=second_user_headers,
        )
        assert response.status_code == 404


class TestWorkspaceMembership:
    async def test_add_documents_rejects_non_completed_documents(
        self,
        client,
        auth_headers,
        test_user: User,
        db_session: AsyncSession,
    ):
        workspace = Workspace(name="Membership", user_id=test_user.id)
        pending_document = Document(
            filename="pending.pdf",
            file_path="uploads/pending.pdf",
            file_size=1024,
            status=DocumentStatus.PENDING,
            user_id=test_user.id,
        )
        db_session.add_all([workspace, pending_document])
        await db_session.flush()

        response = await client.post(
            f"/api/workspaces/{workspace.id}/documents",
            headers=auth_headers,
            json={"document_ids": [pending_document.id]},
        )

        assert response.status_code == 400
        assert "Only completed documents" in response.json()["detail"]

    async def test_add_documents_skips_existing_membership_rows(
        self,
        client,
        auth_headers,
        test_user: User,
        db_session: AsyncSession,
    ):
        workspace = Workspace(name="Membership", user_id=test_user.id)
        document = await _create_completed_document(
            db_session=db_session,
            user_id=test_user.id,
            filename="member.pdf",
        )
        db_session.add(workspace)
        await db_session.flush()
        db_session.add(
            WorkspaceDocument(workspace_id=workspace.id, document_id=document.id)
        )
        await db_session.flush()

        response = await client.post(
            f"/api/workspaces/{workspace.id}/documents",
            headers=auth_headers,
            json={"document_ids": [document.id]},
        )

        assert response.status_code == 200
        assert response.json()["document_count"] == 1

    async def test_add_documents_enforces_workspace_limit(
        self,
        client,
        auth_headers,
        test_user: User,
        db_session: AsyncSession,
    ):
        workspace = Workspace(name="Large workspace", user_id=test_user.id)
        db_session.add(workspace)
        await db_session.flush()

        for idx in range(20):
            document = await _create_completed_document(
                db_session=db_session,
                user_id=test_user.id,
                filename=f"doc-{idx}.pdf",
            )
            db_session.add(
                WorkspaceDocument(
                    workspace_id=workspace.id,
                    document_id=document.id,
                )
            )
        extra_document = await _create_completed_document(
            db_session=db_session,
            user_id=test_user.id,
            filename="doc-extra.pdf",
        )
        await db_session.flush()

        response = await client.post(
            f"/api/workspaces/{workspace.id}/documents",
            headers=auth_headers,
            json={"document_ids": [extra_document.id]},
        )

        assert response.status_code == 400
        assert "more than 20 documents" in response.json()["detail"]

    async def test_remove_document_returns_404_when_missing(
        self,
        client,
        auth_headers,
        test_user: User,
        db_session: AsyncSession,
    ):
        workspace = Workspace(name="Membership", user_id=test_user.id)
        document = await _create_completed_document(
            db_session=db_session,
            user_id=test_user.id,
            filename="member.pdf",
        )
        db_session.add(workspace)
        await db_session.flush()

        response = await client.delete(
            f"/api/workspaces/{workspace.id}/documents/{document.id}",
            headers=auth_headers,
        )

        assert response.status_code == 404

    async def test_remove_document_returns_workspace_detail(
        self,
        client,
        auth_headers,
        test_user: User,
        db_session: AsyncSession,
    ):
        workspace = Workspace(name="Membership", user_id=test_user.id)
        document = await _create_completed_document(
            db_session=db_session,
            user_id=test_user.id,
            filename="member.pdf",
        )
        db_session.add(workspace)
        await db_session.flush()
        db_session.add(
            WorkspaceDocument(
                workspace_id=workspace.id,
                document_id=document.id,
            )
        )
        await db_session.flush()

        response = await client.delete(
            f"/api/workspaces/{workspace.id}/documents/{document.id}",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == workspace.id
        assert data["document_count"] == 0
        assert data["documents"] == []


class TestWorkspaceQuery:
    async def test_query_workspace_returns_cross_document_sources_and_saves_messages(
        self,
        client,
        auth_headers,
        test_user: User,
        db_session: AsyncSession,
    ):
        workspace = Workspace(name="Q&A", user_id=test_user.id)
        db_session.add(workspace)
        await db_session.flush()

        doc_a = await _create_completed_document(
            db_session=db_session,
            user_id=test_user.id,
            filename="report-a.pdf",
        )
        doc_b = await _create_completed_document(
            db_session=db_session,
            user_id=test_user.id,
            filename="report-b.pdf",
        )
        db_session.add_all(
            [
                WorkspaceDocument(workspace_id=workspace.id, document_id=doc_a.id),
                WorkspaceDocument(workspace_id=workspace.id, document_id=doc_b.id),
                Chunk(
                    document_id=doc_a.id,
                    content="A-source",
                    chunk_index=0,
                    embedding=FAKE_EMBEDDING,
                ),
                Chunk(
                    document_id=doc_b.id,
                    content="B-source",
                    chunk_index=0,
                    embedding=FAKE_EMBEDDING,
                ),
            ]
        )
        await db_session.flush()

        with (
            patch(
                "app.services.workspace_service.generate_embedding",
                new=AsyncMock(return_value=FAKE_EMBEDDING),
            ),
            patch(
                "app.services.workspace_service.generate_answer",
                new=AsyncMock(return_value="Combined answer"),
            ) as mock_answer,
        ):
            response = await client.post(
                f"/api/workspaces/{workspace.id}/query",
                headers=auth_headers,
                json={"query": "Summarize both reports"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["answer"] == "Combined answer"
        assert len(data["sources"]) >= 2
        assert {source["document_filename"] for source in data["sources"]} == {
            "report-a.pdf",
            "report-b.pdf",
        }
        assert data["pipeline_meta"]["chunks_retrieved"] == len(data["sources"])
        assert mock_answer.await_args is not None
        chunks_arg = mock_answer.await_args.kwargs["chunks"]
        assert all("document_filename" in chunk for chunk in chunks_arg)

        messages = (
            await db_session.scalars(
                select(Message)
                .where(Message.workspace_id == workspace.id)
                .where(Message.user_id == test_user.id)
                .order_by(Message.created_at.asc(), Message.id.asc())
            )
        ).all()
        assert len(messages) == 2
        assert all(message.document_id is None for message in messages)
        assert messages[0].role == "user"
        assert messages[1].role == "assistant"

    async def test_query_workspace_returns_400_when_empty(
        self,
        client,
        auth_headers,
        test_user: User,
        db_session: AsyncSession,
    ):
        workspace = Workspace(name="Empty", user_id=test_user.id)
        db_session.add(workspace)
        await db_session.flush()

        response = await client.post(
            f"/api/workspaces/{workspace.id}/query",
            headers=auth_headers,
            json={"query": "Any results?"},
        )

        assert response.status_code == 400
        assert response.json()["detail"] == "Workspace has no documents"

    async def test_query_workspace_returns_400_when_no_searchable_chunks(
        self,
        client,
        auth_headers,
        test_user: User,
        db_session: AsyncSession,
    ):
        workspace = Workspace(name="No chunks", user_id=test_user.id)
        db_session.add(workspace)
        await db_session.flush()

        document = await _create_completed_document(
            db_session=db_session,
            user_id=test_user.id,
            filename="no-embeddings.pdf",
        )
        db_session.add(
            WorkspaceDocument(
                workspace_id=workspace.id,
                document_id=document.id,
            )
        )
        await db_session.flush()

        response = await client.post(
            f"/api/workspaces/{workspace.id}/query",
            headers=auth_headers,
            json={"query": "Any indexed content?"},
        )

        assert response.status_code == 400
        assert response.json()["detail"] == "Workspace has no searchable chunks"


class TestWorkspaceMessages:
    async def test_get_workspace_messages_returns_workspace_scoped_history(
        self,
        client,
        auth_headers,
        test_user: User,
        db_session: AsyncSession,
    ):
        workspace = Workspace(name="History", user_id=test_user.id)
        db_session.add(workspace)
        await db_session.flush()

        db_session.add(
            Message(
                workspace_id=workspace.id,
                user_id=test_user.id,
                role="assistant",
                content="Workspace answer",
                sources={
                    "sources": [
                        {
                            "chunk_id": 1,
                            "content": "ctx",
                            "similarity": 0.9,
                            "chunk_index": 0,
                            "document_id": 1,
                            "document_filename": "report.pdf",
                        }
                    ],
                    "pipeline_meta": {
                        "embed_ms": 10,
                        "retrieval_ms": 12,
                        "llm_ms": 30,
                        "total_ms": 52,
                        "top_similarity": 0.9,
                        "avg_similarity": 0.9,
                        "chunks_retrieved": 1,
                        "chunks_above_threshold": 1,
                        "similarity_spread": 0.0,
                        "chat_history_turns_included": 0,
                    },
                },
            )
        )
        await db_session.flush()

        response = await client.get(
            f"/api/workspaces/{workspace.id}/messages",
            headers=auth_headers,
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["total"] == 1
        assert payload["messages"][0]["workspace_id"] == workspace.id
        assert payload["messages"][0]["document_id"] is None
        assert payload["messages"][0]["pipeline_meta"]["chunks_retrieved"] == 1

    async def test_get_workspace_messages_returns_404_for_other_user(
        self,
        client,
        second_user_headers,
        test_user: User,
        db_session: AsyncSession,
    ):
        workspace = Workspace(name="Private", user_id=test_user.id)
        db_session.add(workspace)
        await db_session.flush()

        response = await client.get(
            f"/api/workspaces/{workspace.id}/messages",
            headers=second_user_headers,
        )

        assert response.status_code == 404

    async def test_get_workspace_messages_supports_pipeline_meta_token_fields(
        self,
        client,
        auth_headers,
        test_user: User,
        db_session: AsyncSession,
    ):
        workspace = Workspace(name="Token metadata", user_id=test_user.id)
        db_session.add(workspace)
        await db_session.flush()

        db_session.add(
            Message(
                workspace_id=workspace.id,
                user_id=test_user.id,
                role="assistant",
                content="Workspace answer",
                sources={
                    "sources": [
                        {
                            "chunk_id": 1,
                            "content": "ctx",
                            "similarity": 0.9,
                            "chunk_index": 0,
                            "document_id": 1,
                            "document_filename": "report.pdf",
                        }
                    ],
                    "pipeline_meta": {
                        "embed_ms": 10,
                        "retrieval_ms": 12,
                        "llm_ms": 30,
                        "total_ms": 52,
                        "top_similarity": 0.9,
                        "avg_similarity": 0.9,
                        "chunks_retrieved": 1,
                        "chunks_above_threshold": 1,
                        "similarity_spread": 0.0,
                        "chat_history_turns_included": 0,
                        "embedding_tokens": 7,
                        "llm_input_tokens": 15,
                        "llm_output_tokens": 5,
                    },
                },
            )
        )
        await db_session.flush()

        response = await client.get(
            f"/api/workspaces/{workspace.id}/messages",
            headers=auth_headers,
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["messages"][0]["pipeline_meta"]["embedding_tokens"] == 7
        assert payload["messages"][0]["pipeline_meta"]["llm_input_tokens"] == 15
        assert payload["messages"][0]["pipeline_meta"]["llm_output_tokens"] == 5

    async def test_get_workspace_messages_respects_display_limit(
        self,
        client,
        auth_headers,
        test_user: User,
        db_session: AsyncSession,
    ):
        # Create 3 messages; limit=2 should return the two newest in chronological order
        workspace = Workspace(name="Limit test", user_id=test_user.id)
        db_session.add(workspace)
        await db_session.flush()

        for i in range(3):
            db_session.add(
                Message(
                    workspace_id=workspace.id,
                    user_id=test_user.id,
                    role="user",
                    content=f"Message {i}",
                )
            )
        await db_session.flush()

        with patch("app.services.workspace_service.MESSAGE_HISTORY_DISPLAY_LIMIT", 2):
            response = await client.get(
                f"/api/workspaces/{workspace.id}/messages",
                headers=auth_headers,
            )

        assert response.status_code == 200
        payload = response.json()
        assert payload["total"] == 2
        assert payload["truncated"] is True
        # Most recent 2 messages returned in chronological order (oldest-of-the-two first)
        assert payload["messages"][0]["content"] == "Message 1"
        assert payload["messages"][1]["content"] == "Message 2"

    async def test_get_workspace_messages_not_truncated_when_under_limit(
        self,
        client,
        auth_headers,
        test_user: User,
        db_session: AsyncSession,
    ):
        workspace = Workspace(name="Under limit", user_id=test_user.id)
        db_session.add(workspace)
        await db_session.flush()

        db_session.add(
            Message(
                workspace_id=workspace.id,
                user_id=test_user.id,
                role="user",
                content="Only message",
            )
        )
        await db_session.flush()

        with patch("app.services.workspace_service.MESSAGE_HISTORY_DISPLAY_LIMIT", 2):
            response = await client.get(
                f"/api/workspaces/{workspace.id}/messages",
                headers=auth_headers,
            )

        assert response.status_code == 200
        payload = response.json()
        assert payload["total"] == 1
        assert payload["truncated"] is False
