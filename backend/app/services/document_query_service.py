"""Document query command orchestration.

Coordinates synchronous and streaming query flows for processed documents.
Owns validation, retrieval/LLM pipeline timing, message persistence, and SSE
event semantics used by query endpoints.
"""

import json
import time
from collections.abc import AsyncGenerator

from fastapi import HTTPException
from fastapi.sse import ServerSentEvent
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import MESSAGE_HISTORY_DISPLAY_LIMIT
from app.database import AsyncSessionLocal
from app.models.base import Document, DocumentStatus
from app.models.user import User
from app.repositories.document_repository import document_has_chunks, get_document_for_user
from app.repositories.message_repository import (
    create_message,
    list_messages_for_document_user,
    list_recent_message_pairs_for_document_user,
)
from app.schemas.message import MessageListResponse, MessageResponse
from app.schemas.query import PipelineMeta, QueryRequest, QueryResponse
from app.schemas.search import SearchRequest, SearchResponse, SearchResult
from app.services.anthropic_service import (
    consume_last_answer_usage,
    consume_last_stream_usage,
    generate_answer,
    generate_answer_stream,
)
from app.services.embedding_service import (
    consume_last_embedding_usage_tokens,
    generate_embedding,
)
from app.services.search_service import search_chunks_from_embedding, search_chunks_with_timings
from app.utils.logging_config import get_logger

logger = get_logger(__name__)


def _elapsed_ms(start_time: float) -> int:
    """Convert elapsed perf-counter seconds to integer milliseconds."""
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
    embedding_tokens: int | None = None,
    llm_input_tokens: int | None = None,
    llm_output_tokens: int | None = None,
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
        embedding_tokens=embedding_tokens,
        llm_input_tokens=llm_input_tokens,
        llm_output_tokens=llm_output_tokens,
    )


def _build_query_completed_log_payload(
    *,
    document_id: int,
    user_id: int,
    query_mode: str,
    duration_ms: int,
    pipeline_meta: PipelineMeta,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "event": "query.completed",
        "document_id": document_id,
        "user_id": user_id,
        "query_mode": query_mode,
        "duration_ms": duration_ms,
        "embed_ms": pipeline_meta.embed_ms,
        "retrieval_ms": pipeline_meta.retrieval_ms,
        "llm_ms": pipeline_meta.llm_ms,
        "total_ms": pipeline_meta.total_ms,
        "top_similarity": pipeline_meta.top_similarity,
        "avg_similarity": pipeline_meta.avg_similarity,
        "chunks_retrieved": pipeline_meta.chunks_retrieved,
        "chunks_above_threshold": pipeline_meta.chunks_above_threshold,
        "similarity_spread": pipeline_meta.similarity_spread,
        "chat_history_turns_included": pipeline_meta.chat_history_turns_included,
    }
    if pipeline_meta.embedding_tokens is not None:
        payload["embedding_tokens"] = pipeline_meta.embedding_tokens
    if pipeline_meta.llm_input_tokens is not None:
        payload["llm_input_tokens"] = pipeline_meta.llm_input_tokens
    if pipeline_meta.llm_output_tokens is not None:
        payload["llm_output_tokens"] = pipeline_meta.llm_output_tokens
    return payload


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


async def _build_recent_conversation_history(
    *,
    db: AsyncSession,
    document_id: int,
    user_id: int,
    window_turns: int,
) -> list[dict[str, str]]:
    if window_turns <= 0:
        return []

    rows = await list_recent_message_pairs_for_document_user(
        db=db,
        document_id=document_id,
        user_id=user_id,
        limit=window_turns * 2,
    )
    return [{"role": role, "content": content} for role, content in reversed(rows)]


async def _validate_document_for_query(
    *,
    document_id: int,
    current_user: User,
    db: AsyncSession,
) -> Document:
    """
    Validate ownership, processing status, and chunk existence for query/search endpoints.
    """
    document = await get_document_for_user(
        db=db,
        document_id=document_id,
        user_id=current_user.id,
    )
    if not document:
        raise HTTPException(
            status_code=404,
            detail=f"Document with ID {document_id} not found",
        )

    if document.status != DocumentStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail=f"Document {document_id} not processed yet",
        )

    if not await document_has_chunks(db=db, document_id=document_id):
        raise HTTPException(
            status_code=400,
            detail=f"Document {document_id} has no chunks",
        )

    return document


async def search_document_command(
    *,
    db: AsyncSession,
    document_id: int,
    current_user: User,
    search: SearchRequest,
) -> SearchResponse:
    """Run semantic search against a user's processed document."""
    await _validate_document_for_query(
        document_id=document_id,
        current_user=current_user,
        db=db,
    )

    try:
        results, _, _, _ = await search_chunks_with_timings(
            query=search.query,
            document_id=document_id,
            top_k=search.top_k,
            db=db,
        )
        search_results = [SearchResult(**result) for result in results]
        return SearchResponse(
            query=search.query,
            document_id=document_id,
            results=search_results,
            total_results=len(results),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error(
            "Search failed for document_id=%s, user_id=%s, error_class=%s",
            document_id,
            current_user.id,
            type(exc).__name__,
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="Search failed")


async def query_document_command(
    *,
    db: AsyncSession,
    document_id: int,
    current_user: User,
    body: QueryRequest,
    history_window_turns: int,
    similarity_threshold: float,
) -> QueryResponse:
    """Execute the synchronous query pipeline and persist a complete chat turn."""
    query_start = time.perf_counter()
    logger.info(
        f"Query request for document_id={document_id}, user_id={current_user.id}, query_chars={len(body.query)}"
    )
    logger.info(
        "query.started",
        extra={
            "event": "query.started",
            "document_id": document_id,
            "user_id": current_user.id,
            "query_chars": len(body.query),
            "query_mode": "sync",
        },
    )

    try:
        await _validate_document_for_query(
            document_id=document_id,
            current_user=current_user,
            db=db,
        )

        conversation_history = await _build_recent_conversation_history(
            db=db,
            document_id=document_id,
            user_id=current_user.id,
            window_turns=history_window_turns,
        )

        # Keep user/assistant persistence in one transaction so failures do not leave
        # a dangling user-only turn in history.
        user_message = await create_message(
            db=db,
            document_id=document_id,
            user_id=current_user.id,
            role="user",
            content=body.query,
            sources=None,
        )

        pipeline_start = time.perf_counter()
        search_results, embed_ms, retrieval_ms, embedding_tokens = await search_chunks_with_timings(
            query=body.query,
            document_id=document_id,
            top_k=5,
            db=db,
        )

        llm_start = time.perf_counter()
        answer = await generate_answer(
            query=body.query,
            chunks=search_results,
            conversation_history=conversation_history,
        )
        llm_usage = consume_last_answer_usage()
        llm_ms = _elapsed_ms(llm_start)
        total_ms = _elapsed_ms(pipeline_start)

        sources = [SearchResult(**result) for result in search_results]
        pipeline_meta = _build_pipeline_meta(
            search_results=search_results,
            conversation_history=conversation_history,
            embed_ms=embed_ms,
            retrieval_ms=retrieval_ms,
            llm_ms=llm_ms,
            total_ms=total_ms,
            similarity_threshold=similarity_threshold,
            embedding_tokens=embedding_tokens,
            llm_input_tokens=llm_usage.input_tokens if llm_usage is not None else None,
            llm_output_tokens=llm_usage.output_tokens if llm_usage is not None else None,
        )

        sources_dict = [source.model_dump() for source in sources]
        assistant_message = await create_message(
            db=db,
            document_id=document_id,
            user_id=current_user.id,
            role="assistant",
            content=answer,
            sources=_build_message_sources_payload(
                sources=sources_dict,
                pipeline_meta=pipeline_meta,
            ),
        )
        # Commit only after both turns exist to preserve turn-pair integrity.
        await db.commit()

        logger.info(
            f"Saved messages for document_id={document_id}: user_msg_id={user_message.id}, assistant_msg_id={assistant_message.id}"
        )
        logger.info(
            "query.completed",
            extra=_build_query_completed_log_payload(
                document_id=document_id,
                user_id=current_user.id,
                query_mode="sync",
                duration_ms=total_ms,
                pipeline_meta=pipeline_meta,
            ),
        )

        return QueryResponse(
            query=body.query,
            answer=answer,
            sources=sources,
            pipeline_meta=pipeline_meta,
        )
    except HTTPException as exc:
        await db.rollback()
        logger.warning(
            "query.failed",
            extra={
                "event": "query.failed",
                "document_id": document_id,
                "user_id": current_user.id,
                "query_mode": "sync",
                "duration_ms": _elapsed_ms(query_start),
                "status_code": exc.status_code,
                "error_class": "HTTPException",
            },
        )
        raise
    except ValueError as exc:
        await db.rollback()
        logger.warning(
            "query.failed",
            extra={
                "event": "query.failed",
                "document_id": document_id,
                "user_id": current_user.id,
                "query_mode": "sync",
                "duration_ms": _elapsed_ms(query_start),
                "error_class": type(exc).__name__,
            },
        )
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        await db.rollback()
        logger.info(
            "query.failed",
            extra={
                "event": "query.failed",
                "document_id": document_id,
                "user_id": current_user.id,
                "query_mode": "sync",
                "duration_ms": _elapsed_ms(query_start),
                "error_class": type(exc).__name__,
            },
        )
        logger.error(
            "Query failed for document_id=%s, user_id=%s, error_class=%s",
            document_id,
            current_user.id,
            type(exc).__name__,
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="Query failed")


async def query_document_stream_events_command(
    *,
    db: AsyncSession,
    document_id: int,
    current_user: User,
    body: QueryRequest,
    history_window_turns: int,
    similarity_threshold: float,
) -> AsyncGenerator[ServerSentEvent, None]:
    """Stream query tokens over SSE and persist the final assistant response."""
    query_start = time.perf_counter()
    embedding_tokens: int | None = None
    logger.info(
        f"Streaming query request for document_id={document_id}, user_id={current_user.id}, query_chars={len(body.query)}"
    )
    logger.info(
        "query.started",
        extra={
            "event": "query.started",
            "document_id": document_id,
            "user_id": current_user.id,
            "query_chars": len(body.query),
            "query_mode": "stream",
        },
    )

    try:
        await _validate_document_for_query(
            document_id=document_id,
            current_user=current_user,
            db=db,
        )

        conversation_history = await _build_recent_conversation_history(
            db=db,
            document_id=document_id,
            user_id=current_user.id,
            window_turns=history_window_turns,
        )

        # Transaction 1: persist user message + run retrieval, then commit.
        await create_message(
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
        embedding_tokens = consume_last_embedding_usage_tokens()

        retrieval_start = time.perf_counter()
        search_results = await search_chunks_from_embedding(
            db=db,
            document_id=document_id,
            query_embedding=query_embedding,
            top_k=5,
        )
        retrieval_ms = _elapsed_ms(retrieval_start)

        sources = [SearchResult(**result) for result in search_results]
        sources_dict = [source.model_dump() for source in sources]

        await db.commit()
    except HTTPException as exc:
        await db.rollback()
        logger.warning(
            "query.failed",
            extra={
                "event": "query.failed",
                "document_id": document_id,
                "user_id": current_user.id,
                "query_mode": "stream",
                "stage": "validation_or_setup",
                "duration_ms": _elapsed_ms(query_start),
                "status_code": exc.status_code,
                "error_class": "HTTPException",
            },
        )
        raise
    except ValueError as exc:
        await db.rollback()
        logger.warning(
            "query.failed",
            extra={
                "event": "query.failed",
                "document_id": document_id,
                "user_id": current_user.id,
                "query_mode": "stream",
                "stage": "setup",
                "duration_ms": _elapsed_ms(query_start),
                "error_class": type(exc).__name__,
            },
        )
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        await db.rollback()
        logger.info(
            "query.failed",
            extra={
                "event": "query.failed",
                "document_id": document_id,
                "user_id": current_user.id,
                "query_mode": "stream",
                "stage": "setup",
                "duration_ms": _elapsed_ms(query_start),
                "error_class": type(exc).__name__,
            },
        )
        logger.error(
            "Streaming query setup failed for document_id=%s, user_id=%s, error_class=%s",
            document_id,
            current_user.id,
            type(exc).__name__,
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="Query failed")

    async def _persist_assistant_message(
        *,
        content: str,
        sources_payload: dict | None,
    ) -> int | None:
        """Persist assistant output in an isolated write session."""
        try:
            # Streaming can outlive request-scoped session state; use a dedicated
            # session for terminal assistant writes.
            async with AsyncSessionLocal() as write_db:
                assistant_message = await create_message(
                    db=write_db,
                    document_id=document_id,
                    user_id=current_user.id,
                    role="assistant",
                    content=content,
                    sources=sources_payload,
                )
                message_id = assistant_message.id
                await write_db.commit()
                return message_id
        except Exception as exc:
            logger.error(
                "Failed to persist streamed assistant message for document_id=%s, user_id=%s, error_class=%s",
                document_id,
                current_user.id,
                type(exc).__name__,
                exc_info=True,
            )
            return None

    async def _stream_events() -> AsyncGenerator[ServerSentEvent, None]:
        answer_tokens: list[str] = []
        llm_start = time.perf_counter()

        try:
            # SSE contract: send sources before token events so clients can attach
            # citations while tokens arrive.
            yield ServerSentEvent(event="sources", raw_data=json.dumps(sources_dict))
            async for token in generate_answer_stream(
                query=body.query,
                chunks=search_results,
                conversation_history=conversation_history,
            ):
                answer_tokens.append(token)
                yield ServerSentEvent(event="token", raw_data=token)
        except Exception as exc:
            logger.info(
                "query.failed",
                extra={
                    "event": "query.failed",
                    "document_id": document_id,
                    "user_id": current_user.id,
                    "query_mode": "stream",
                    "stage": "llm_stream",
                    "duration_ms": _elapsed_ms(query_start),
                    "error_class": type(exc).__name__,
                },
            )
            logger.error(
                "Streaming query failed for document_id=%s, user_id=%s, error_class=%s",
                document_id,
                current_user.id,
                type(exc).__name__,
                exc_info=True,
            )
            # If partial output exists, persist it as the assistant turn instead of
            # dropping the completion from chat history.
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
        llm_usage = consume_last_stream_usage()
        pipeline_meta = _build_pipeline_meta(
            search_results=search_results,
            conversation_history=conversation_history,
            embed_ms=embed_ms,
            retrieval_ms=retrieval_ms,
            llm_ms=llm_ms,
            total_ms=_elapsed_ms(pipeline_start),
            similarity_threshold=similarity_threshold,
            embedding_tokens=embedding_tokens,
            llm_input_tokens=llm_usage.input_tokens if llm_usage is not None else None,
            llm_output_tokens=llm_usage.output_tokens if llm_usage is not None else None,
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
            logger.warning(
                "query.failed",
                extra={
                    "event": "query.failed",
                    "document_id": document_id,
                    "user_id": current_user.id,
                    "query_mode": "stream",
                    "stage": "persist_assistant",
                    "duration_ms": _elapsed_ms(query_start),
                    "error_class": "MessagePersistError",
                },
            )
            # Best effort fallback so chat history still has a terminal assistant turn.
            await _persist_assistant_message(
                content="I encountered an internal error saving the final response. Please retry.",
                sources_payload=None,
            )
            yield ServerSentEvent(event="error", raw_data=json.dumps({"detail": "Query failed"}))
            return

        logger.info(
            "query.completed",
            extra=_build_query_completed_log_payload(
                document_id=document_id,
                user_id=current_user.id,
                query_mode="stream",
                duration_ms=_elapsed_ms(query_start),
                pipeline_meta=pipeline_meta,
            ),
        )

        yield ServerSentEvent(
            event="done",
            raw_data=json.dumps({"message_id": assistant_message_id}),
        )

    return _stream_events()


async def get_document_messages_command(
    *,
    db: AsyncSession,
    document_id: int,
    current_user: User,
) -> MessageListResponse:
    """Return chat history for a document after enforcing ownership checks."""
    document = await get_document_for_user(
        db=db,
        document_id=document_id,
        user_id=current_user.id,
    )

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    raw_messages = await list_messages_for_document_user(
        db=db,
        document_id=document_id,
        user_id=current_user.id,
        limit=MESSAGE_HISTORY_DISPLAY_LIMIT,
    )
    # Repository returns DESC order (newest first); reverse for chronological display.
    truncated = len(raw_messages) == MESSAGE_HISTORY_DISPLAY_LIMIT
    messages = list(reversed(raw_messages))

    response_messages: list[MessageResponse] = []
    for message in messages:
        sources, pipeline_meta = _extract_sources_and_pipeline_meta(message.sources)
        response_messages.append(
            MessageResponse(
                id=message.id,
                document_id=message.document_id,
                user_id=message.user_id,
                role=message.role,
                content=message.content,
                sources=sources,
                pipeline_meta=pipeline_meta,
                created_at=message.created_at,
            )
        )

    return MessageListResponse(
        messages=response_messages,
        total=len(response_messages),
        truncated=truncated,
    )
