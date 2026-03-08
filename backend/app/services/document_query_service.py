import json
import time
from collections.abc import AsyncGenerator

from fastapi import HTTPException
from fastapi.sse import ServerSentEvent
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.base import Document, DocumentStatus
from app.models.user import User
from app.schemas.query import PipelineMeta, QueryRequest, QueryResponse
from app.schemas.search import SearchRequest, SearchResponse, SearchResult
from app.services.anthropic_service import generate_answer, generate_answer_stream
from app.services.document_service import (
    add_message,
    get_recent_conversation_history,
    get_user_document,
    user_document_has_chunks,
)
from app.services.embedding_service import generate_embedding
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
            status_code=404,
            detail=f"Document with ID {document_id} not found",
        )

    if document.status != DocumentStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail=f"Document {document_id} not processed yet",
        )

    if not await user_document_has_chunks(db=db, document_id=document_id):
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
    await _validate_document_for_query(
        document_id=document_id,
        current_user=current_user,
        db=db,
    )

    try:
        results, _, _ = await search_chunks_with_timings(
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
    logger.info(
        f"Query request for document_id={document_id}, user_id={current_user.id}, query_chars={len(body.query)}"
    )

    await _validate_document_for_query(
        document_id=document_id,
        current_user=current_user,
        db=db,
    )

    try:
        conversation_history = await get_recent_conversation_history(
            db=db,
            document_id=document_id,
            user_id=current_user.id,
            window_turns=history_window_turns,
        )

        user_message = await add_message(
            db=db,
            document_id=document_id,
            user_id=current_user.id,
            role="user",
            content=body.query,
            sources=None,
        )

        pipeline_start = time.perf_counter()
        search_results, embed_ms, retrieval_ms = await search_chunks_with_timings(
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
        )

        sources_dict = [source.model_dump() for source in sources]
        assistant_message = await add_message(
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
        await db.commit()

        logger.info(
            f"Saved messages for document_id={document_id}: user_msg_id={user_message.id}, assistant_msg_id={assistant_message.id}"
        )

        return QueryResponse(
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
    logger.info(
        f"Streaming query request for document_id={document_id}, user_id={current_user.id}, query_chars={len(body.query)}"
    )

    await _validate_document_for_query(
        document_id=document_id,
        current_user=current_user,
        db=db,
    )

    try:
        conversation_history = await get_recent_conversation_history(
            db=db,
            document_id=document_id,
            user_id=current_user.id,
            window_turns=history_window_turns,
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
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        await db.rollback()
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
        try:
            async with AsyncSessionLocal() as write_db:
                assistant_message = await add_message(
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
            yield ServerSentEvent(event="sources", raw_data=json.dumps(sources_dict))
            async for token in generate_answer_stream(
                query=body.query,
                chunks=search_results,
                conversation_history=conversation_history,
            ):
                answer_tokens.append(token)
                yield ServerSentEvent(event="token", raw_data=token)
        except Exception as exc:
            logger.error(
                "Streaming query failed for document_id=%s, user_id=%s, error_class=%s",
                document_id,
                current_user.id,
                type(exc).__name__,
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
            similarity_threshold=similarity_threshold,
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

    return _stream_events()
