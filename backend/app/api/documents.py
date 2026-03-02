import json
import time
from collections.abc import AsyncGenerator

from app.api.dependencies import get_current_user
from app.database import AsyncSessionLocal, get_db
from app.models.base import Chunk, Document, DocumentStatus
from app.models.message import Message
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
from app.services.anthropic_service import generate_answer, generate_answer_stream
from app.services.embedding_service import generate_embedding
from app.services.queue_service import enqueue_document_processing
from app.services.search_service import search_chunks
from app.services.storage_service import delete_file
from app.utils.file_utils import save_upload_file, validate_file_upload
from app.utils.logging_config import get_logger
from app.utils.rate_limit import get_user_or_ip_key, limiter
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import EventSourceResponse
from fastapi.sse import ServerSentEvent, format_sse_event
from sqlalchemy import literal, select
from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)

router = APIRouter()


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
    embed_ms: int,
    retrieval_ms: int,
    llm_ms: int,
    total_ms: int,
) -> PipelineMeta:
    similarities = [result["similarity"] for result in search_results]
    top_similarity = max(similarities) if similarities else 0.0
    avg_similarity = (sum(similarities) / len(similarities)) if similarities else 0.0

    return PipelineMeta(
        embed_ms=embed_ms,
        retrieval_ms=retrieval_ms,
        llm_ms=llm_ms,
        total_ms=total_ms,
        top_similarity=round(top_similarity, 4),
        avg_similarity=round(avg_similarity, 4),
        chunks_retrieved=len(search_results),
    )


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
    distance_expr = Chunk.embedding.cosine_distance(query_embedding).label("distance")
    stmt = (
        select(Chunk.id, Chunk.content, Chunk.chunk_index, distance_expr)
        .where(Chunk.document_id == document_id)
        .where(Chunk.embedding.isnot(None))
        .order_by(distance_expr)
        .limit(top_k)
    )

    rows = (await db.execute(stmt)).all()

    results: list[dict] = []
    for chunk_id, content, chunk_index, distance in rows:
        results.append(
            {
                "chunk_id": chunk_id,
                "content": content,
                "similarity": round(1 - distance, 4),
                "chunk_index": chunk_index,
            }
        )
    return results


async def _validate_document_for_query(
    *,
    document_id: int,
    current_user: User,
    db: AsyncSession,
) -> Document:
    """
    Validate ownership, processing status, and chunk existence for query/search endpoints.
    """
    document = await db.scalar(
        select(Document).where(
            Document.id == document_id,
            Document.user_id == current_user.id,
        )
    )
    if not document:
        raise HTTPException(
            status_code=404, detail=f"Document with ID {document_id} not found"
        )

    if document.status != DocumentStatus.COMPLETED:
        raise HTTPException(status_code=400, detail=f"Document {document_id} not processed yet")

    chunk_exists = await db.scalar(
        select(literal(1)).where(Chunk.document_id == document_id).limit(1)
    )
    if chunk_exists is None:
        raise HTTPException(status_code=400, detail=f"Document {document_id} has no chunks")

    return document


@router.post("/upload", response_model=UploadResponse, status_code=201)
@limiter.limit("5/hour", key_func=get_user_or_ip_key)
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Upload a PDF document.

    Steps:
    1. Validate file (type, size)
    2. Save to disk
    3. Create database record
    4. Return document info
    """

    logger.info(f"Uploading: {file.filename}")

    validate_file_upload(file)

    file_path, file_size = await save_upload_file(file)

    document = Document(
        filename=file.filename,
        file_path=file_path,
        file_size=file_size,
        status=DocumentStatus.PENDING,
        user_id=current_user.id,
    )

    db.add(document)
    await db.commit()
    await db.refresh(document)  # Get auto-generated ID
    try:
        await enqueue_document_processing(document.id)
    except Exception as exc:
        # Persist queue failure on the document so the user can retry explicitly.
        document.status = DocumentStatus.FAILED
        document.error_message = "Upload succeeded, but queueing failed. Please retry."
        await db.commit()
        logger.error(f"Queueing failed for document_id={document.id}: {exc}", exc_info=True)
        raise HTTPException(
            status_code=503,
            detail="Document uploaded but could not be queued for processing.",
        )

    logger.info(f"Upload complete and queued: document_id={document.id}")

    return UploadResponse(
        id=document.id,
        user_id=current_user.id,
        filename=document.filename,
        file_size=document.file_size,
        status=document.status,
        message="File uploaded successfully. Processing started in background.",
    )


@router.get("/", response_model=DocumentListResponse)
@limiter.limit("20/hour", key_func=get_user_or_ip_key)
async def get_documents(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get all uploaded documents.
    """
    stmt = (
        select(Document)
        .where(Document.user_id == current_user.id)
        .order_by(Document.uploaded_at.desc())
    )
    documents = (await db.scalars(stmt)).all()

    return DocumentListResponse(
        documents=[DocumentResponse.model_validate(d) for d in documents],
        total=len(documents),
    )


@router.get("/{document_id}", response_model=DocumentResponse)
@limiter.limit("30/hour", key_func=get_user_or_ip_key)
async def get_document(
    request: Request,
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get a specific document by ID.
    """
    stmt = (
        select(Document)
        .where(Document.id == document_id)
        .where(Document.user_id == current_user.id)
    )
    document = await db.scalar(stmt)

    if not document:
        raise HTTPException(
            status_code=404, detail=f"Document with ID {document_id} not found"
        )

    return document


@router.get("/{document_id}/status", response_model=DocumentStatusResponse)
@limiter.limit("120/minute", key_func=get_user_or_ip_key)
async def get_document_status(
    request: Request,
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get lightweight processing status for one document.

    Intended for frequent polling from the dashboard while background jobs run.
    """
    stmt = (
        select(Document)
        .where(Document.id == document_id)
        .where(Document.user_id == current_user.id)
    )
    document = await db.scalar(stmt)

    if not document:
        raise HTTPException(
            status_code=404, detail=f"Document with ID {document_id} not found"
        )

    return DocumentStatusResponse(
        id=document.id,
        status=document.status,
        processed_at=document.processed_at,
        error_message=document.error_message,
    )


@router.delete("/{document_id}")
@limiter.limit("10/hour", key_func=get_user_or_ip_key)
async def delete_document(
    request: Request,
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Delete a document and its file.
    """
    logger.info(f"Deleting document_id={document_id}")

    stmt = (
        select(Document)
        .where(Document.id == document_id)
        .where(Document.user_id == current_user.id)
    )
    document = await db.scalar(stmt)

    if not document:
        raise HTTPException(
            status_code=404, detail=f"Document with ID {document_id} not found"
        )

    # Delete file from configured storage backend.
    await delete_file(document.file_path)

    # Delete from database (cascades to chunks)
    await db.delete(document)
    await db.commit()

    logger.info(f"Successfully deleted document_id={document_id}")
    return {"message": f"Document {document_id} deleted successfully"}


# PROCESS DOCUMENT
@router.post("/{document_id}/process", status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("5/hour", key_func=get_user_or_ip_key)
async def process_document(
    request: Request,
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Queue document processing in the background worker.
    """
    logger.info(f"Queue processing request for document_id={document_id}")

    stmt = (
        select(Document)
        .where(Document.id == document_id)
        .where(Document.user_id == current_user.id)
    )
    document = await db.scalar(stmt)

    if not document:
        raise HTTPException(
            status_code=404, detail=f"Document with ID {document_id} not found"
        )

    if document.status == DocumentStatus.COMPLETED:
        raise HTTPException(status_code=400, detail=f"Document {document_id} already processed")

    if document.status == DocumentStatus.PROCESSING:
        raise HTTPException(
            status_code=400,
            detail=f"Document {document_id} is currently being processed",
        )

    if document.status == DocumentStatus.FAILED:
        # Reset stale failure details before retry.
        document.status = DocumentStatus.PENDING
        document.error_message = None
        document.processed_at = None
        await db.commit()

    try:
        enqueued = await enqueue_document_processing(document_id)
    except Exception as exc:
        document.status = DocumentStatus.FAILED
        document.error_message = "Queueing failed. Please retry processing."
        await db.commit()
        logger.error(
            f"Failed to enqueue document_id={document_id}: {exc}",
            exc_info=True,
        )
        raise HTTPException(status_code=503, detail="Failed to queue document processing")

    message = (
        f"Document {document_id} processing already queued"
        if not enqueued
        else f"Document {document_id} queued for background processing"
    )

    return {"message": message, "document_id": document_id}


@router.post("/{document_id}/search", response_model=SearchResponse)
@limiter.limit("15/hour", key_func=get_user_or_ip_key)
async def search_document(
    request: Request,
    search: SearchRequest,
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _validate_document_for_query(
        document_id=document_id,
        current_user=current_user,
        db=db,
    )

    try:
        results = await search_chunks(
            query=search.query, document_id=document_id, top_k=search.top_k, db=db
        )

        search_results = [SearchResult(**result) for result in results]
        return SearchResponse(
            query=search.query,
            document_id=document_id,
            results=search_results,
            total_results=len(results),
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        logger.error(f"Search failed for document_id={document_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Search failed")


@router.post("/{document_id}/query", response_model=QueryResponse)
@limiter.shared_limit("10/hour", scope="query", key_func=get_user_or_ip_key)
async def query_document(
    request: Request,
    document_id: int,
    body: QueryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Ask a question about a document and get an AI-generated answer.

    Uses semantic search to find relevant chunks, then sends them to Claude
    for natural language answer generation. Persists both user and assistant
    messages to the database for chat history.
    """

    logger.info(f"Query request for document_id={document_id}: '{body.query}'")

    await _validate_document_for_query(
        document_id=document_id,
        current_user=current_user,
        db=db,
    )

    try:
        # Save user message to database
        user_message = Message(
            document_id=document_id,
            user_id=current_user.id,
            role="user",
            content=body.query,
            sources=None,
        )
        db.add(user_message)
        await db.flush()

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

        llm_start = time.perf_counter()
        answer = await generate_answer(query=body.query, chunks=search_results)
        llm_ms = _elapsed_ms(llm_start)
        total_ms = _elapsed_ms(pipeline_start)

        # Format sources for response
        sources = [SearchResult(**result) for result in search_results]
        pipeline_meta = _build_pipeline_meta(
            search_results=search_results,
            embed_ms=embed_ms,
            retrieval_ms=retrieval_ms,
            llm_ms=llm_ms,
            total_ms=total_ms,
        )

        # Save assistant message to database
        # Convert SearchResult objects to dicts for JSONB storage
        sources_dict = [source.model_dump() for source in sources]
        assistant_message = Message(
            document_id=document_id,
            user_id=current_user.id,
            role="assistant",
            content=answer,
            sources=sources_dict,
        )
        db.add(assistant_message)
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

    except ValueError as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        await db.rollback()
        logger.error(f"Query failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Query failed")


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
    logger.info(f"Streaming query request for document_id={document_id}: '{body.query}'")

    await _validate_document_for_query(
        document_id=document_id,
        current_user=current_user,
        db=db,
    )

    try:
        # Transaction 1: persist user message + run retrieval, then commit.
        user_message = Message(
            document_id=document_id,
            user_id=current_user.id,
            role="user",
            content=body.query,
            sources=None,
        )
        db.add(user_message)
        await db.flush()

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
        logger.error(f"Streaming query setup failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Query failed")

    async def _stream_events() -> AsyncGenerator[ServerSentEvent, None]:
        answer_tokens: list[str] = []
        llm_start = time.perf_counter()

        try:
            yield ServerSentEvent(event="sources", raw_data=json.dumps(sources_dict))
            async for token in generate_answer_stream(query=body.query, chunks=search_results):
                answer_tokens.append(token)
                yield ServerSentEvent(event="token", raw_data=token)
        except Exception as e:
            logger.error(f"Streaming query failed for document_id={document_id}: {e}", exc_info=True)
            yield ServerSentEvent(event="error", raw_data=json.dumps({"detail": "Query failed"}))
            return

        llm_ms = _elapsed_ms(llm_start)
        pipeline_meta = _build_pipeline_meta(
            search_results=search_results,
            embed_ms=embed_ms,
            retrieval_ms=retrieval_ms,
            llm_ms=llm_ms,
            total_ms=_elapsed_ms(pipeline_start),
        )
        yield ServerSentEvent(event="meta", raw_data=pipeline_meta.model_dump_json())

        answer = "".join(answer_tokens)
        try:
            # Transaction 2: open a new session and persist assistant response.
            async with AsyncSessionLocal() as write_db:
                assistant_message = Message(
                    document_id=document_id,
                    user_id=current_user.id,
                    role="assistant",
                    content=answer,
                    sources=sources_dict,
                )
                write_db.add(assistant_message)
                await write_db.commit()
                await write_db.refresh(assistant_message)
        except Exception as e:
            logger.error(
                f"Failed to persist streamed assistant message for document_id={document_id}: {e}",
                exc_info=True,
            )
            yield ServerSentEvent(event="error", raw_data=json.dumps({"detail": "Query failed"}))
            return

        yield ServerSentEvent(
            event="done",
            raw_data=json.dumps({"message_id": assistant_message.id}),
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
    # Verify document exists and user owns it
    stmt = (
        select(Document)
        .where(Document.id == document_id)
        .where(Document.user_id == current_user.id)
    )
    document = await db.scalar(stmt)

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # Get messages for this document and user, ordered by creation time
    msg_stmt = (
        select(Message)
        .where(Message.document_id == document_id)
        .where(Message.user_id == current_user.id)
        .order_by(Message.created_at.asc())
    )
    messages = (await db.scalars(msg_stmt)).all()

    return MessageListResponse(
        messages=[MessageResponse.model_validate(msg) for msg in messages],
        total=len(messages),
    )
