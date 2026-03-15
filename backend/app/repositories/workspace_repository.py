from sqlalchemy import delete, func, literal, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import Chunk, Document
from app.models.workspace import Workspace, WorkspaceDocument


async def create_workspace(
    *,
    db: AsyncSession,
    user_id: int,
    name: str,
) -> Workspace:
    workspace = Workspace(user_id=user_id, name=name)
    db.add(workspace)
    await db.flush()
    return workspace


async def list_workspaces_for_user_with_counts(
    *,
    db: AsyncSession,
    user_id: int,
) -> list[tuple[Workspace, int]]:
    counts_subquery = (
        select(
            WorkspaceDocument.workspace_id,
            func.count(WorkspaceDocument.id).label("document_count"),
        )
        .group_by(WorkspaceDocument.workspace_id)
        .subquery()
    )

    stmt = (
        select(
            Workspace,
            func.coalesce(counts_subquery.c.document_count, 0),
        )
        .outerjoin(
            counts_subquery,
            counts_subquery.c.workspace_id == Workspace.id,
        )
        .where(Workspace.user_id == user_id)
        .order_by(Workspace.created_at.desc(), Workspace.id.desc())
    )
    rows = (await db.execute(stmt)).all()
    return [(workspace, int(document_count)) for workspace, document_count in rows]


async def get_workspace_for_user(
    *,
    db: AsyncSession,
    workspace_id: int,
    user_id: int,
) -> Workspace | None:
    stmt = (
        select(Workspace)
        .where(Workspace.id == workspace_id)
        .where(Workspace.user_id == user_id)
    )
    return await db.scalar(stmt)


async def count_workspace_documents(
    *,
    db: AsyncSession,
    workspace_id: int,
) -> int:
    stmt = (
        select(func.count(WorkspaceDocument.id))
        .where(WorkspaceDocument.workspace_id == workspace_id)
    )
    count = await db.scalar(stmt)
    return int(count or 0)


async def list_workspace_documents(
    *,
    db: AsyncSession,
    workspace_id: int,
) -> list[Document]:
    stmt = (
        select(Document)
        .join(WorkspaceDocument, WorkspaceDocument.document_id == Document.id)
        .where(WorkspaceDocument.workspace_id == workspace_id)
        .order_by(WorkspaceDocument.added_at.asc(), WorkspaceDocument.id.asc())
    )
    return list((await db.scalars(stmt)).all())


async def list_workspace_document_ids(
    *,
    db: AsyncSession,
    workspace_id: int,
) -> set[int]:
    stmt = select(WorkspaceDocument.document_id).where(
        WorkspaceDocument.workspace_id == workspace_id
    )
    rows = (await db.execute(stmt)).all()
    return {document_id for (document_id,) in rows}


async def get_documents_for_user_by_ids(
    *,
    db: AsyncSession,
    user_id: int,
    document_ids: list[int],
) -> list[Document]:
    if not document_ids:
        return []

    stmt = (
        select(Document)
        .where(Document.user_id == user_id)
        .where(Document.id.in_(document_ids))
    )
    return list((await db.scalars(stmt)).all())


async def add_workspace_documents(
    *,
    db: AsyncSession,
    workspace_id: int,
    document_ids: list[int],
) -> None:
    for document_id in document_ids:
        db.add(
            WorkspaceDocument(
                workspace_id=workspace_id,
                document_id=document_id,
            )
        )
    await db.flush()


async def remove_workspace_document(
    *,
    db: AsyncSession,
    workspace_id: int,
    document_id: int,
) -> bool:
    # Single DELETE…RETURNING avoids a SELECT + DELETE round trip (see refresh_token_repository pattern).
    stmt = (
        delete(WorkspaceDocument)
        .where(WorkspaceDocument.workspace_id == workspace_id)
        .where(WorkspaceDocument.document_id == document_id)
        .returning(WorkspaceDocument.id)
    )
    deleted_id = await db.scalar(stmt)
    return deleted_id is not None


async def workspace_has_searchable_chunks(
    *,
    db: AsyncSession,
    workspace_id: int,
) -> bool:
    stmt = (
        select(literal(1))
        .select_from(WorkspaceDocument)
        .join(Chunk, Chunk.document_id == WorkspaceDocument.document_id)
        .where(WorkspaceDocument.workspace_id == workspace_id)
        .where(Chunk.embedding.isnot(None))
        .limit(1)
    )
    return await db.scalar(stmt) is not None


async def search_workspace_chunks_by_embedding(
    *,
    db: AsyncSession,
    workspace_id: int,
    query_embedding: list[float],
    top_k: int,
) -> list[tuple[int, str, int, int | None, int | None, int, str, float]]:
    distance_expr = Chunk.embedding.cosine_distance(query_embedding).label("distance")
    stmt = (
        select(
            Chunk.id,
            Chunk.content,
            Chunk.chunk_index,
            Chunk.page_start,
            Chunk.page_end,
            Chunk.document_id,
            Document.filename,
            distance_expr,
        )
        .join(WorkspaceDocument, WorkspaceDocument.document_id == Chunk.document_id)
        .join(Document, Document.id == Chunk.document_id)
        .where(WorkspaceDocument.workspace_id == workspace_id)
        .where(Chunk.embedding.isnot(None))
        .order_by(distance_expr)
        .limit(top_k)
    )
    rows = (await db.execute(stmt)).all()
    return [
        (
            chunk_id,
            content,
            chunk_index,
            page_start,
            page_end,
            document_id,
            document_filename,
            distance,
        )
        for (
            chunk_id,
            content,
            chunk_index,
            page_start,
            page_end,
            document_id,
            document_filename,
            distance,
        ) in rows
    ]
