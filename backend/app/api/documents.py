import json
import time
from collections.abc import AsyncGenerator

from pydantic import ValidationError
from app.api.dependencies import get_current_user
from app.database import AsyncSessionLocal, get_db
from app.models.base import Document, DocumentStatus
from app.models.user import User
from app.schemas.document import (
    DocumentListResponse,
    DocumentResponse,
    DocumentStatusResponse,
    UploadResponse,
)
from app.schemas.message import MessageListResponse, MessageResponse
from app.schemas.query import PipelineMeta, QueryRequest, QueryResponse
from app.schemas.search import SearchRequest, SearchResponse, SearchResult
from app.services.anthropic_service import generate_answer_stream
from app.services.document_commands_service import (
    delete_document_command,
    get_document_command,
    get_document_file_command,
    get_document_status_command,
    list_documents_command,
    process_document_command,
    upload_document_command,
)
from app.services.document_query_service import (
    query_document_command,
    search_document_command,
)
from app.services.embedding_service import generate_embedding
from app.services.document_service import (
    add_message,
    get_recent_conversation_history,
    get_user_document,
    list_user_document_messages,
    user_document_has_chunks,
)
from app.services.search_service import search_chunks_from_embedding
from app.utils.logging_config import get_logger
from app.utils.rate_limit import get_user_or_ip_key, limiter
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import EventSourceResponse
from fastapi.sse import ServerSentEvent, format_sse_event
from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)

router = APIRouter()
CONVERSATION_HISTORY_WINDOW_TURNS = 5
# Practical confidence threshold calibrated from mini-eval snapshots (2026-03-07).
SIMILARITY_THRESHOLD = 0.60


def _elapsed_ms(start_time: float) -> int:
    """Convert elapsed perf-counter seconds to integer milliseconds."""
    return int((time.perf_counter() - start_time) * 1000)


def _encode_sse_event(event: ServerSentEvent) -> bytes:
    """Encode a FastAPI ServerSentEvent instance into wire-format bytes."""
    if event.raw_data is not None:
        data_str: str | None = event.raw_data
    elif event.data is not None:
        data_str = json.dumps(event.data)
    else:
        data_str = None

    return format_sse_event(
        data_str=data_str,
        event=event.event,
        id=event.id,
        retry=event.retry,
        comment=event.comment,
    )


def _build_pipeline_meta(
    *,
    search_results: list[dict],
    conversation_history: list[dict[str, str]],
    embed_ms: int,
    retrieval_ms: int,
    llm_ms: int,
    total_ms: int,
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
            1 for similarity in similarities if similarity > SIMILARITY_THRESHOLD
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


def _extract_sources_and_pipeline_meta(raw_sources: object) -> tuple[list[dict] | None, PipelineMeta | None]:
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


async def _search_chunks_from_embedding(
    *,
    db: AsyncSession,
    document_id: int,
    query_embedding: list[float],
    top_k: int,
) -> list[dict]:
    """
    Search document chunks using a precomputed query embedding.
    """
    return await search_chunks_from_embedding(
        db=db,
        document_id=document_id,
        query_embedding=query_embedding,
        top_k=top_k,
    )


async def _validate_document_for_query(
    *,
    document_id: int,
    current_user: User,
    db: AsyncSession,
) -> Document:
    """
    Validate ownership, processing status, and chunk existence for query/search endpoints.
    """
    document = await get_user_document(
        db=db,
        document_id=document_id,
        user_id=current_user.id,
    )
    if not document:
        raise HTTPException(
            status_code=404, detail=f"Document with ID {document_id} not found"
        )

    if document.status != DocumentStatus.COMPLETED:
        raise HTTPException(status_code=400, detail=f"Document {document_id} not processed yet")

    if not await user_document_has_chunks(db=db, document_id=document_id):
        raise HTTPException(status_code=400, detail=f"Document {document_id} has no chunks")

    return document


async def _get_recent_conversation_history(
    *,
    db: AsyncSession,
    document_id: int,
    user_id: int,
    window_turns: int = CONVERSATION_HISTORY_WINDOW_TURNS,
) -> list[dict[str, str]]:
    """
    Fetch the last N conversation turns for a document thread (oldest -> newest).

    A turn is treated as two messages (user + assistant), so we load up to N*2
    recent messages and reverse them to chronological order.
    """
    return await get_recent_conversation_history(
        db=db,
        document_id=document_id,
        user_id=user_id,
        window_turns=window_turns,
    )


@router.post("/upload", response_model=UploadResponse, status_code=201)
@limiter.limit("5/hour", key_func=get_user_or_ip_key)
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await upload_document_command(
        db=db,
        current_user=current_user,
        file=file,
    )


@router.get("/", response_model=DocumentListResponse)
@limiter.limit("20/hour", key_func=get_user_or_ip_key)
async def get_documents(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await list_documents_command(
        db=db,
        user_id=current_user.id,
    )


@router.get("/{document_id}", response_model=DocumentResponse)
@limiter.limit("30/hour", key_func=get_user_or_ip_key)
async def get_document(
    request: Request,
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await get_document_command(
        db=db,
        document_id=document_id,
        user_id=current_user.id,
    )


@router.get("/{document_id}/file")
@limiter.limit("30/hour", key_func=get_user_or_ip_key)
async def get_document_file(
    request: Request,
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await get_document_file_command(
        db=db,
        document_id=document_id,
        user_id=current_user.id,
    )


@router.get("/{document_id}/status", response_model=DocumentStatusResponse)
@limiter.limit("120/minute", key_func=get_user_or_ip_key)
async def get_document_status(
    request: Request,
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await get_document_status_command(
        db=db,
        document_id=document_id,
        user_id=current_user.id,
    )


@router.delete("/{document_id}")
@limiter.limit("10/hour", key_func=get_user_or_ip_key)
async def delete_document(
    request: Request,
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await delete_document_command(
        db=db,
        document_id=document_id,
        current_user=current_user,
    )


# PROCESS DOCUMENT
@router.post("/{document_id}/process", status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("5/hour", key_func=get_user_or_ip_key)
async def process_document(
    request: Request,
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await process_document_command(
        db=db,
        document_id=document_id,
        user_id=current_user.id,
    )


@router.post("/{document_id}/search", response_model=SearchResponse)
@limiter.limit("15/hour", key_func=get_user_or_ip_key)
async def search_document(
    request: Request,
    search: SearchRequest,
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await search_document_command(
        db=db,
        document_id=document_id,
        current_user=current_user,
        search=search,
    )


@router.post("/{document_id}/query", response_model=QueryResponse)
@limiter.shared_limit("10/hour", scope="query", key_func=get_user_or_ip_key)
async def query_document(
    request: Request,
    document_id: int,
    body: QueryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await query_document_command(
        db=db,
        document_id=document_id,
        current_user=current_user,
        body=body,
        history_window_turns=CONVERSATION_HISTORY_WINDOW_TURNS,
        similarity_threshold=SIMILARITY_THRESHOLD,
    )


@router.post("/{document_id}/query/stream")
@limiter.shared_limit("10/hour", scope="query", key_func=get_user_or_ip_key)
async def query_document_stream(
    request: Request,
    document_id: int,
    body: QueryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Stream an AI-generated answer over SSE for a document query.
    """
    logger.info(
        f"Streaming query request for document_id={document_id}, user_id={current_user.id}, query_chars={len(body.query)}"
    )

    await _validate_document_for_query(
        document_id=document_id,
        current_user=current_user,
        db=db,
    )

    try:
        conversation_history = await _get_recent_conversation_history(
            db=db,
            document_id=document_id,
            user_id=current_user.id,
        )

        # Transaction 1: persist user message + run retrieval, then commit.
        await add_message(
            db=db,
            document_id=document_id,
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
        search_results = await _search_chunks_from_embedding(
            db=db,
            document_id=document_id,
            query_embedding=query_embedding,
            top_k=5,
        )
        retrieval_ms = _elapsed_ms(retrieval_start)

        sources = [SearchResult(**result) for result in search_results]
        sources_dict = [source.model_dump() for source in sources]

        await db.commit()
    except ValueError as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        await db.rollback()
        logger.error(
            "Streaming query setup failed for document_id=%s, user_id=%s, error_class=%s",
            document_id,
            current_user.id,
            type(e).__name__,
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="Query failed")

    async def _stream_events() -> AsyncGenerator[ServerSentEvent, None]:
        async def _persist_assistant_message(
            *,
            content: str,
                sources_payload: dict | None,
        ) -> int | None:
            try:
                async with AsyncSessionLocal() as write_db:
                    assistant_message = await add_message(
                        document_id=document_id,
                        user_id=current_user.id,
                        role="assistant",
                        content=content,
                        sources=sources_payload,
                        db=write_db,
                    )
                    message_id = assistant_message.id
                    await write_db.commit()
                    return message_id
            except Exception as e:
                logger.error(
                    "Failed to persist streamed assistant message for document_id=%s, user_id=%s, error_class=%s",
                    document_id,
                    current_user.id,
                    type(e).__name__,
                    exc_info=True,
                )
                return None

        answer_tokens: list[str] = []
        llm_start = time.perf_counter()

        try:
            yield ServerSentEvent(event="sources", raw_data=json.dumps(sources_dict))
            async for token in generate_answer_stream(
                query=body.query,
                chunks=search_results,
                conversation_history=conversation_history,
            ):
                answer_tokens.append(token)
                yield ServerSentEvent(event="token", raw_data=token)
        except Exception as e:
            logger.error(
                "Streaming query failed for document_id=%s, user_id=%s, error_class=%s",
                document_id,
                current_user.id,
                type(e).__name__,
                exc_info=True,
            )
            partial_answer = "".join(answer_tokens).strip()
            assistant_content = (
                partial_answer
                if partial_answer
                else "I encountered an error communicating with the AI service. Please try again later."
            )
            await _persist_assistant_message(
                content=assistant_content,
                sources_payload=_build_message_sources_payload(
                    sources=sources_dict,
                    pipeline_meta=None,
                ),
            )
            yield ServerSentEvent(event="error", raw_data=json.dumps({"detail": "Query failed"}))
            return

        llm_ms = _elapsed_ms(llm_start)
        pipeline_meta = _build_pipeline_meta(
            search_results=search_results,
            conversation_history=conversation_history,
            embed_ms=embed_ms,
            retrieval_ms=retrieval_ms,
            llm_ms=llm_ms,
            total_ms=_elapsed_ms(pipeline_start),
        )
        yield ServerSentEvent(event="meta", raw_data=pipeline_meta.model_dump_json())

        answer = "".join(answer_tokens)
        assistant_message_id = await _persist_assistant_message(
            content=answer,
            sources_payload=_build_message_sources_payload(
                sources=sources_dict,
                pipeline_meta=pipeline_meta,
            ),
        )
        if assistant_message_id is None:
            # Best effort fallback so chat history still has a terminal assistant turn.
            await _persist_assistant_message(
                content="I encountered an internal error saving the final response. Please retry.",
                sources_payload=None,
            )
            yield ServerSentEvent(event="error", raw_data=json.dumps({"detail": "Query failed"}))
            return

        yield ServerSentEvent(
            event="done",
            raw_data=json.dumps({"message_id": assistant_message_id}),
        )

    async def _encoded_stream_events() -> AsyncGenerator[bytes, None]:
        async for event in _stream_events():
            yield _encode_sse_event(event)

    return EventSourceResponse(_encoded_stream_events())


@router.get("/{document_id}/messages", response_model=MessageListResponse)
@limiter.limit("30/hour", key_func=get_user_or_ip_key)
async def get_document_messages(
    request: Request,
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get all messages for a specific document.

    Returns messages in chronological order (oldest first).
    Only returns messages for documents the user owns.
    """
    document = await get_user_document(
        db=db,
        document_id=document_id,
        user_id=current_user.id,
    )

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    messages = await list_user_document_messages(
        db=db,
        document_id=document_id,
        user_id=current_user.id,
    )

    response_messages: list[MessageResponse] = []
    for msg in messages:
        sources, pipeline_meta = _extract_sources_and_pipeline_meta(msg.sources)
        response_messages.append(
            MessageResponse(
                id=msg.id,
                document_id=msg.document_id,
                user_id=msg.user_id,
                role=msg.role,
                content=msg.content,
                sources=sources,
                pipeline_meta=pipeline_meta,
                created_at=msg.created_at,
            )
        )

    return MessageListResponse(
        messages=response_messages,
        total=len(messages),
    )
