from datetime import datetime

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.base import Chunk, Document, DocumentStatus
from app.models.user import User


async def get_user_by_username_or_email(
    *,
    db: AsyncSession,
    username: str,
    email: str,
) -> User | None:
    stmt = select(User).where(or_(User.username == username, User.email == email))
    return await db.scalar(stmt)


async def create_demo_user(
    *,
    db: AsyncSession,
    username: str,
    email: str,
    hashed_password: str,
) -> User:
    demo_user = User(
        username=username,
        email=email,
        hashed_password=hashed_password,
        is_demo=True,
    )
    db.add(demo_user)
    await db.flush()
    return demo_user


async def list_documents_with_chunks_for_user(
    *,
    db: AsyncSession,
    user_id: int,
) -> list[Document]:
    stmt = (
        select(Document)
        .where(Document.user_id == user_id)
        .options(selectinload(Document.chunks))
    )
    return list((await db.scalars(stmt)).all())


async def delete_documents(
    *,
    db: AsyncSession,
    documents: list[Document],
) -> None:
    for document in documents:
        await db.delete(document)
    await db.flush()


async def create_completed_document(
    *,
    db: AsyncSession,
    user_id: int,
    filename: str,
    file_path: str,
    file_size: int,
    processed_at: datetime,
) -> Document:
    document = Document(
        filename=filename,
        file_path=file_path,
        file_size=file_size,
        status=DocumentStatus.COMPLETED,
        user_id=user_id,
        processed_at=processed_at,
        error_message=None,
    )
    db.add(document)
    await db.flush()
    return document


async def create_document_chunk(
    *,
    db: AsyncSession,
    document_id: int,
    content: str,
    chunk_index: int,
    page_start: int | None,
    page_end: int | None,
    embedding: list[float],
) -> None:
    db.add(
        Chunk(
            document_id=document_id,
            content=content,
            chunk_index=chunk_index,
            page_start=page_start,
            page_end=page_end,
            embedding=embedding,
        )
    )
