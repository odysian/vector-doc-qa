from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.message import Message


async def create_message(
    *,
    db: AsyncSession,
    document_id: int,
    user_id: int,
    role: str,
    content: str,
    sources: dict | None,
) -> Message:
    message = Message(
        document_id=document_id,
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
) -> list[Message]:
    stmt = (
        select(Message)
        .where(Message.document_id == document_id)
        .where(Message.user_id == user_id)
        .order_by(Message.created_at.asc())
    )
    return list((await db.scalars(stmt)).all())
