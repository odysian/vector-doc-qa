import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.workspace import Workspace
from app.repositories.message_repository import create_message


class TestCreateMessageContextContract:
    async def test_create_message_raises_when_no_context_id(
        self,
        db_session: AsyncSession,
        test_user,
    ):
        with pytest.raises(
            ValueError, match="Exactly one of document_id or workspace_id must be provided"
        ):
            await create_message(
                db=db_session,
                user_id=test_user.id,
                role="user",
                content="hello",
                sources=None,
            )

    async def test_create_message_raises_when_both_context_ids_set(
        self,
        db_session: AsyncSession,
        test_user,
        test_document,
    ):
        workspace = Workspace(name="ctx", user_id=test_user.id)
        db_session.add(workspace)
        await db_session.flush()

        with pytest.raises(
            ValueError, match="Exactly one of document_id or workspace_id must be provided"
        ):
            await create_message(
                db=db_session,
                document_id=test_document.id,
                workspace_id=workspace.id,
                user_id=test_user.id,
                role="user",
                content="hello",
                sources=None,
            )

    async def test_create_message_allows_workspace_context_only(
        self,
        db_session: AsyncSession,
        test_user,
    ):
        workspace = Workspace(name="ctx", user_id=test_user.id)
        db_session.add(workspace)
        await db_session.flush()

        message = await create_message(
            db=db_session,
            workspace_id=workspace.id,
            user_id=test_user.id,
            role="assistant",
            content="workspace answer",
            sources={"sources": []},
        )

        assert message.workspace_id == workspace.id
        assert message.document_id is None
