from sqlalchemy import literal, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import Chunk, Document, DocumentStatus


async def create_document(
    *,
    db: AsyncSession,
    filename: str,
    file_path: str,
    file_size: int,
    user_id: int,
    status: DocumentStatus = DocumentStatus.PENDING,
) -> Document:
    document = Document(
        filename=filename,
        file_path=file_path,
        file_size=file_size,
        status=status,
        user_id=user_id,
    )
    db.add(document)
    await db.flush()
    return document


async def list_documents_for_user(
    *,
    db: AsyncSession,
    user_id: int,
) -> list[Document]:
    stmt = (
        select(Document)
        .where(Document.user_id == user_id)
        .order_by(Document.uploaded_at.desc())
    )
    return (await db.scalars(stmt)).all()


async def get_document_for_user(
    *,
    db: AsyncSession,
    document_id: int,
    user_id: int,
) -> Document | None:
    stmt = (
        select(Document)
        .where(Document.id == document_id)
        .where(Document.user_id == user_id)
    )
    return await db.scalar(stmt)


async def get_document_by_id(
    *,
    db: AsyncSession,
    document_id: int,
) -> Document | None:
    stmt = select(Document).where(Document.id == document_id)
    return await db.scalar(stmt)


async def delete_document(
    *,
    db: AsyncSession,
    document: Document,
) -> None:
    await db.delete(document)


async def document_has_chunks(
    *,
    db: AsyncSession,
    document_id: int,
) -> bool:
    chunk_exists = await db.scalar(
        select(literal(1)).where(Chunk.document_id == document_id).limit(1)
    )
    return chunk_exists is not None


async def search_document_chunks_by_embedding(
    *,
    db: AsyncSession,
    document_id: int,
    query_embedding: list[float],
    top_k: int,
) -> list[tuple[int, str, int, int | None, int | None, float]]:
    distance_expr = Chunk.embedding.cosine_distance(query_embedding).label("distance")
    stmt = (
        select(
            Chunk.id,
            Chunk.content,
            Chunk.chunk_index,
            Chunk.page_start,
            Chunk.page_end,
            distance_expr,
        )
        .where(Chunk.document_id == document_id)
        .where(Chunk.embedding.isnot(None))
        .order_by(distance_expr)
        .limit(top_k)
    )
    return (await db.execute(stmt)).all()

