from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.message import Message


async def create_message(
    *,
    db: AsyncSession,
    document_id: int | None = None,
    workspace_id: int | None = None,
    user_id: int,
    role: str,
    content: str,
    sources: dict | None,
) -> Message:
    if (document_id is None) == (workspace_id is None):
        raise ValueError("Exactly one of document_id or workspace_id must be provided")

    message = Message(
        document_id=document_id,
        workspace_id=workspace_id,
        user_id=user_id,
        role=role,
        content=content,
        sources=sources,
    )
    db.add(message)
    await db.flush()
    return message


async def list_recent_message_pairs_for_document_user(
    *,
    db: AsyncSession,
    document_id: int,
    user_id: int,
    limit: int,
) -> list[tuple[str, str]]:
    stmt = (
        select(Message.role, Message.content)
        .where(Message.document_id == document_id)
        .where(Message.user_id == user_id)
        .order_by(Message.created_at.desc(), Message.id.desc())
        .limit(limit)
    )
    rows = (await db.execute(stmt)).all()
    return [(role, content) for role, content in rows]


async def list_messages_for_document_user(
    *,
    db: AsyncSession,
    document_id: int,
    user_id: int,
    limit: int | None = None,
) -> list[Message]:
    stmt = (
        select(Message)
        .where(Message.document_id == document_id)
        .where(Message.user_id == user_id)
        .order_by(Message.created_at.asc())
    )
    if limit is not None:
        stmt = stmt.limit(limit)
    return list((await db.scalars(stmt)).all())


async def list_recent_message_pairs_for_workspace_user(
    *,
    db: AsyncSession,
    workspace_id: int,
    user_id: int,
    limit: int,
) -> list[tuple[str, str]]:
    stmt = (
        select(Message.role, Message.content)
        .where(Message.workspace_id == workspace_id)
        .where(Message.user_id == user_id)
        .order_by(Message.created_at.desc(), Message.id.desc())
        .limit(limit)
    )
    rows = (await db.execute(stmt)).all()
    return [(role, content) for role, content in rows]


async def list_messages_for_workspace_user(
    *,
    db: AsyncSession,
    workspace_id: int,
    user_id: int,
    limit: int | None = None,
) -> list[Message]:
    stmt = (
        select(Message)
        .where(Message.workspace_id == workspace_id)
        .where(Message.user_id == user_id)
        .order_by(Message.created_at.asc())
    )
    if limit is not None:
        stmt = stmt.limit(limit)
    return list((await db.scalars(stmt)).all())
