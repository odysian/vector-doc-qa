from app.api.dependencies import get_current_user
from app.config import settings
from app.database import get_db
from app.models.base import Document, DocumentStatus
from app.models.message import Message
from app.models.user import User
from app.schemas.document import (
    DocumentListResponse,
    DocumentResponse,
    DocumentStatusResponse,
    UploadResponse,
)
from app.schemas.message import MessageListResponse, MessageResponse
from app.schemas.query import QueryRequest, QueryResponse
from app.schemas.search import SearchRequest, SearchResponse, SearchResult
from app.services.anthropic_service import generate_answer
from app.services.queue_service import enqueue_document_processing
from app.services.search_service import search_chunks
from app.utils.file_utils import save_upload_file, validate_file_upload
from app.utils.logging_config import get_logger
from app.utils.rate_limit import get_user_or_ip_key, limiter
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

logger = get_logger(__name__)

router = APIRouter()


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

    # Delete file from disk
    full_path = settings.get_upload_path().parent / document.file_path
    full_path.unlink(missing_ok=True)

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

    # Eagerly load chunks to avoid lazy-loading MissingGreenlet in async
    stmt = (
        select(Document)
        .options(selectinload(Document.chunks))
        .where(Document.id == document_id)
        .where(Document.user_id == current_user.id)
    )
    document = await db.scalar(stmt)

    if not document:
        raise HTTPException(
            status_code=404, detail=f"Document with ID {document_id} not found"
        )
    if document.status != DocumentStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail=f"Document {document_id} not processed yet",
        )

    if not document.chunks:
        raise HTTPException(
            status_code=400,
            detail=f"Document {document_id} has no chunks",
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
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.post("/{document_id}/query", response_model=QueryResponse)
@limiter.limit("10/hour", key_func=get_user_or_ip_key)
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

    # Verify document exists and user owns it
    # Eagerly load chunks to avoid lazy-loading MissingGreenlet in async
    stmt = (
        select(Document)
        .options(selectinload(Document.chunks))
        .where(Document.id == document_id)
        .where(Document.user_id == current_user.id)
    )
    document = await db.scalar(stmt)

    if not document:
        raise HTTPException(
            status_code=404, detail=f"Document with ID {document_id} not found"
        )
    if document.status != DocumentStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail=f"Document {document_id} not processed yet",
        )

    if not document.chunks:
        raise HTTPException(
            status_code=400,
            detail=f"Document {document_id} has no chunks",
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

        # Perform RAG search and generate answer
        search_results = await search_chunks(
            query=body.query, document_id=document_id, top_k=5, db=db
        )

        answer = await generate_answer(query=body.query, chunks=search_results)

        # Format sources for response
        sources = [SearchResult(**result) for result in search_results]

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

        return QueryResponse(query=body.query, answer=answer, sources=sources)

    except ValueError as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        await db.rollback()
        logger.error(f"Query failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


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
    stmt = (
        select(Message)
        .where(Message.document_id == document_id)
        .where(Message.user_id == current_user.id)
        .order_by(Message.created_at.asc())
    )
    messages = (await db.scalars(stmt)).all()

    return MessageListResponse(
        messages=[MessageResponse.model_validate(msg) for msg in messages],
        total=len(messages),
    )
