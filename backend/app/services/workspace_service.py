from datetime import datetime, timezone
import time
from typing import Any

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import DocumentStatus
from app.models.user import User
from app.models.workspace import Workspace
from app.repositories.message_repository import (
    create_message,
    list_messages_for_workspace_user,
    list_recent_message_pairs_for_workspace_user,
)
from app.repositories.workspace_repository import (
    add_workspace_documents,
    count_workspace_documents,
    create_workspace,
    get_documents_for_user_by_ids,
    get_workspace_for_user,
    list_workspace_document_ids,
    list_workspace_documents,
    list_workspaces_for_user_with_counts,
    remove_workspace_document,
    search_workspace_chunks_by_embedding,
    workspace_has_searchable_chunks,
)
from app.schemas.document import DocumentResponse
from app.schemas.message import MessageListResponse, MessageResponse
from app.schemas.query import PipelineMeta, QueryRequest
from app.schemas.workspace import (
    WorkspaceAddDocuments,
    WorkspaceCreate,
    WorkspaceDetailResponse,
    WorkspaceListResponse,
    WorkspaceQueryResponse,
    WorkspaceResponse,
    WorkspaceSearchResult,
    WorkspaceUpdate,
)
from app.services.anthropic_service import generate_answer
from app.services.embedding_service import generate_embedding
from app.utils.logging_config import get_logger

logger = get_logger(__name__)

MAX_WORKSPACE_DOCUMENTS = 20
WORKSPACE_MEMBERSHIP_LOCK_NAMESPACE = 104


def _elapsed_ms(start_time: float) -> int:
    return int((time.perf_counter() - start_time) * 1000)


def _build_pipeline_meta(
    *,
    search_results: list[dict],
    conversation_history: list[dict[str, str]],
    embed_ms: int,
    retrieval_ms: int,
    llm_ms: int,
    total_ms: int,
    similarity_threshold: float,
) -> PipelineMeta:
    similarities = [result["similarity"] for result in search_results]
    top_similarity = max(similarities) if similarities else 0.0
    avg_similarity = (sum(similarities) / len(similarities)) if similarities else 0.0
    similarity_spread = (max(similarities) - min(similarities)) if similarities else 0.0

    return PipelineMeta(
        embed_ms=embed_ms,
        retrieval_ms=retrieval_ms,
        llm_ms=llm_ms,
        total_ms=total_ms,
        top_similarity=round(top_similarity, 4),
        avg_similarity=round(avg_similarity, 4),
        chunks_retrieved=len(search_results),
        chunks_above_threshold=sum(
            1 for similarity in similarities if similarity > similarity_threshold
        ),
        similarity_spread=round(similarity_spread, 4),
        chat_history_turns_included=len(conversation_history) // 2,
    )


def _build_message_sources_payload(
    *,
    sources: list[dict],
    pipeline_meta: PipelineMeta | None,
) -> dict:
    payload: dict = {"sources": sources}
    if pipeline_meta is not None:
        payload["pipeline_meta"] = pipeline_meta.model_dump()
    return payload


def _extract_sources_and_pipeline_meta(
    raw_sources: object,
) -> tuple[list[dict] | None, PipelineMeta | None]:
    if isinstance(raw_sources, list):
        return raw_sources, None

    if not isinstance(raw_sources, dict):
        return None, None

    sources_payload = raw_sources.get("sources")
    sources = sources_payload if isinstance(sources_payload, list) else None

    pipeline_meta_payload = raw_sources.get("pipeline_meta")
    if not isinstance(pipeline_meta_payload, dict):
        return sources, None

    try:
        pipeline_meta = PipelineMeta.model_validate(pipeline_meta_payload)
    except ValidationError:
        pipeline_meta = None

    return sources, pipeline_meta


async def _get_workspace_for_user_or_404(
    *,
    db: AsyncSession,
    workspace_id: int,
    user_id: int,
) -> Workspace:
    workspace = await get_workspace_for_user(
        db=db,
        workspace_id=workspace_id,
        user_id=user_id,
    )
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return workspace


def _to_workspace_response(
    *,
    workspace: Workspace,
    document_count: int,
) -> WorkspaceResponse:
    return WorkspaceResponse(
        id=workspace.id,
        name=workspace.name,
        user_id=workspace.user_id,
        created_at=workspace.created_at,
        updated_at=workspace.updated_at,
        document_count=document_count,
    )


async def _build_workspace_detail_response(
    *,
    db: AsyncSession,
    workspace: Workspace,
) -> WorkspaceDetailResponse:
    documents = await list_workspace_documents(db=db, workspace_id=workspace.id)
    return WorkspaceDetailResponse(
        id=workspace.id,
        name=workspace.name,
        user_id=workspace.user_id,
        created_at=workspace.created_at,
        updated_at=workspace.updated_at,
        document_count=len(documents),
        documents=[DocumentResponse.model_validate(document) for document in documents],
    )


async def _build_recent_conversation_history(
    *,
    db: AsyncSession,
    workspace_id: int,
    user_id: int,
    window_turns: int,
) -> list[dict[str, str]]:
    if window_turns <= 0:
        return []

    rows = await list_recent_message_pairs_for_workspace_user(
        db=db,
        workspace_id=workspace_id,
        user_id=user_id,
        limit=window_turns * 2,
    )
    return [{"role": role, "content": content} for role, content in reversed(rows)]


async def _lock_workspace_membership_mutation(
    *,
    db: AsyncSession,
    workspace_id: int,
) -> None:
    """
    Serialize workspace membership updates per workspace.

    This transaction-scoped advisory lock prevents parallel add requests from
    both passing the 20-document capacity check.
    """
    await db.execute(
        text(
            "SELECT pg_advisory_xact_lock(:lock_namespace, :workspace_id)"
        ),
        {
            "lock_namespace": WORKSPACE_MEMBERSHIP_LOCK_NAMESPACE,
            "workspace_id": workspace_id,
        },
    )


async def create_workspace_command(
    *,
    db: AsyncSession,
    current_user: User,
    body: WorkspaceCreate,
) -> WorkspaceResponse:
    if current_user.is_demo:
        raise HTTPException(status_code=403, detail="Demo account cannot create workspaces")

    workspace = await create_workspace(
        db=db,
        user_id=current_user.id,
        name=body.name,
    )
    await db.commit()
    await db.refresh(workspace)

    return _to_workspace_response(workspace=workspace, document_count=0)


async def list_workspaces_command(
    *,
    db: AsyncSession,
    current_user: User,
) -> WorkspaceListResponse:
    workspaces_with_counts = await list_workspaces_for_user_with_counts(
        db=db,
        user_id=current_user.id,
    )

    workspaces = [
        _to_workspace_response(workspace=workspace, document_count=document_count)
        for workspace, document_count in workspaces_with_counts
    ]
    return WorkspaceListResponse(workspaces=workspaces, total=len(workspaces))


async def get_workspace_command(
    *,
    db: AsyncSession,
    workspace_id: int,
    current_user: User,
) -> WorkspaceDetailResponse:
    workspace = await _get_workspace_for_user_or_404(
        db=db,
        workspace_id=workspace_id,
        user_id=current_user.id,
    )
    return await _build_workspace_detail_response(db=db, workspace=workspace)


async def update_workspace_command(
    *,
    db: AsyncSession,
    workspace_id: int,
    current_user: User,
    body: WorkspaceUpdate,
) -> WorkspaceResponse:
    if current_user.is_demo:
        raise HTTPException(status_code=403, detail="Demo account cannot modify workspaces")

    workspace = await _get_workspace_for_user_or_404(
        db=db,
        workspace_id=workspace_id,
        user_id=current_user.id,
    )
    workspace.name = body.name
    workspace.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(workspace)

    document_count = await count_workspace_documents(db=db, workspace_id=workspace.id)
    return _to_workspace_response(workspace=workspace, document_count=document_count)


async def delete_workspace_command(
    *,
    db: AsyncSession,
    workspace_id: int,
    current_user: User,
) -> dict[str, str]:
    if current_user.is_demo:
        raise HTTPException(status_code=403, detail="Demo account cannot modify workspaces")

    workspace = await _get_workspace_for_user_or_404(
        db=db,
        workspace_id=workspace_id,
        user_id=current_user.id,
    )
    await db.delete(workspace)
    await db.commit()
    return {"message": f"Workspace {workspace_id} deleted successfully"}


async def add_workspace_documents_command(
    *,
    db: AsyncSession,
    workspace_id: int,
    current_user: User,
    body: WorkspaceAddDocuments,
) -> WorkspaceDetailResponse:
    if current_user.is_demo:
        raise HTTPException(status_code=403, detail="Demo account cannot modify workspaces")

    workspace = await _get_workspace_for_user_or_404(
        db=db,
        workspace_id=workspace_id,
        user_id=current_user.id,
    )

    requested_document_ids = list(dict.fromkeys(body.document_ids))
    documents = await get_documents_for_user_by_ids(
        db=db,
        user_id=current_user.id,
        document_ids=requested_document_ids,
    )
    if len(documents) != len(requested_document_ids):
        raise HTTPException(status_code=404, detail="One or more documents not found")

    if any(document.status != DocumentStatus.COMPLETED for document in documents):
        raise HTTPException(
            status_code=400,
            detail="Only completed documents can be added to workspaces",
        )

    await _lock_workspace_membership_mutation(
        db=db,
        workspace_id=workspace_id,
    )

    existing_document_ids = await list_workspace_document_ids(
        db=db,
        workspace_id=workspace_id,
    )
    new_document_ids = [
        document_id
        for document_id in requested_document_ids
        if document_id not in existing_document_ids
    ]

    if len(existing_document_ids) + len(new_document_ids) > MAX_WORKSPACE_DOCUMENTS:
        raise HTTPException(
            status_code=400,
            detail=f"Workspace cannot contain more than {MAX_WORKSPACE_DOCUMENTS} documents",
        )

    if new_document_ids:
        await add_workspace_documents(
            db=db,
            workspace_id=workspace_id,
            document_ids=new_document_ids,
        )

    await db.commit()
    return await _build_workspace_detail_response(db=db, workspace=workspace)


async def remove_workspace_document_command(
    *,
    db: AsyncSession,
    workspace_id: int,
    document_id: int,
    current_user: User,
) -> WorkspaceDetailResponse:
    if current_user.is_demo:
        raise HTTPException(status_code=403, detail="Demo account cannot modify workspaces")

    workspace = await _get_workspace_for_user_or_404(
        db=db,
        workspace_id=workspace_id,
        user_id=current_user.id,
    )

    removed = await remove_workspace_document(
        db=db,
        workspace_id=workspace_id,
        document_id=document_id,
    )
    if not removed:
        raise HTTPException(status_code=404, detail="Document not found in workspace")

    await db.commit()
    return await _build_workspace_detail_response(db=db, workspace=workspace)


async def query_workspace_command(
    *,
    db: AsyncSession,
    workspace_id: int,
    current_user: User,
    body: QueryRequest,
    history_window_turns: int,
    similarity_threshold: float,
) -> WorkspaceQueryResponse:
    logger.info(
        "Workspace query request for workspace_id=%s, user_id=%s, query_chars=%s",
        workspace_id,
        current_user.id,
        len(body.query),
    )

    await _get_workspace_for_user_or_404(
        db=db,
        workspace_id=workspace_id,
        user_id=current_user.id,
    )

    document_count = await count_workspace_documents(db=db, workspace_id=workspace_id)
    if document_count == 0:
        raise HTTPException(status_code=400, detail="Workspace has no documents")

    if not await workspace_has_searchable_chunks(db=db, workspace_id=workspace_id):
        raise HTTPException(status_code=400, detail="Workspace has no searchable chunks")

    try:
        conversation_history = await _build_recent_conversation_history(
            db=db,
            workspace_id=workspace_id,
            user_id=current_user.id,
            window_turns=history_window_turns,
        )

        await create_message(
            db=db,
            workspace_id=workspace_id,
            user_id=current_user.id,
            role="user",
            content=body.query,
            sources=None,
        )

        pipeline_start = time.perf_counter()

        embedding_start = time.perf_counter()
        query_embedding = await generate_embedding(body.query)
        embed_ms = _elapsed_ms(embedding_start)

        retrieval_start = time.perf_counter()
        search_rows = await search_workspace_chunks_by_embedding(
            db=db,
            workspace_id=workspace_id,
            query_embedding=query_embedding,
            top_k=5,
        )
        retrieval_ms = _elapsed_ms(retrieval_start)

        search_results: list[dict[str, Any]] = []
        for (
            chunk_id,
            content,
            chunk_index,
            page_start,
            page_end,
            document_id,
            document_filename,
            distance,
        ) in search_rows:
            search_results.append(
                {
                    "chunk_id": chunk_id,
                    "content": content,
                    "similarity": round(1 - distance, 4),
                    "chunk_index": chunk_index,
                    "page_start": page_start,
                    "page_end": page_end,
                    "document_id": document_id,
                    "document_filename": document_filename,
                }
            )

        llm_start = time.perf_counter()
        answer = await generate_answer(
            query=body.query,
            chunks=search_results,
            conversation_history=conversation_history,
        )
        llm_ms = _elapsed_ms(llm_start)
        total_ms = _elapsed_ms(pipeline_start)

        sources = [
            WorkspaceSearchResult.model_validate(result) for result in search_results
        ]
        pipeline_meta = _build_pipeline_meta(
            search_results=search_results,
            conversation_history=conversation_history,
            embed_ms=embed_ms,
            retrieval_ms=retrieval_ms,
            llm_ms=llm_ms,
            total_ms=total_ms,
            similarity_threshold=similarity_threshold,
        )

        await create_message(
            db=db,
            workspace_id=workspace_id,
            user_id=current_user.id,
            role="assistant",
            content=answer,
            sources=_build_message_sources_payload(
                sources=[source.model_dump() for source in sources],
                pipeline_meta=pipeline_meta,
            ),
        )
        await db.commit()

        return WorkspaceQueryResponse(
            query=body.query,
            answer=answer,
            sources=sources,
            pipeline_meta=pipeline_meta,
        )
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        await db.rollback()
        logger.error(
            "Workspace query failed for workspace_id=%s, user_id=%s, error_class=%s",
            workspace_id,
            current_user.id,
            type(exc).__name__,
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="Query failed")


async def list_workspace_messages_command(
    *,
    db: AsyncSession,
    workspace_id: int,
    current_user: User,
) -> MessageListResponse:
    await _get_workspace_for_user_or_404(
        db=db,
        workspace_id=workspace_id,
        user_id=current_user.id,
    )

    messages = await list_messages_for_workspace_user(
        db=db,
        workspace_id=workspace_id,
        user_id=current_user.id,
    )

    response_messages: list[MessageResponse] = []
    for message in messages:
        sources, pipeline_meta = _extract_sources_and_pipeline_meta(message.sources)
        response_messages.append(
            MessageResponse(
                id=message.id,
                document_id=message.document_id,
                workspace_id=message.workspace_id,
                user_id=message.user_id,
                role=message.role,
                content=message.content,
                sources=sources,
                pipeline_meta=pipeline_meta,
                created_at=message.created_at,
            )
        )

    return MessageListResponse(messages=response_messages, total=len(response_messages))
