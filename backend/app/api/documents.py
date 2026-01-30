from app.api.dependencies import get_current_user
from app.config import settings
from app.database import get_db
from app.models.base import Chunk, Document, DocumentStatus
from app.models.message import Message
from app.models.user import User
from app.schemas.document import DocumentListResponse, DocumentResponse, UploadResponse
from app.schemas.message import MessageListResponse, MessageResponse
from app.schemas.query import QueryRequest, QueryResponse
from app.schemas.search import SearchRequest, SearchResponse, SearchResult
from app.services.anthropic_service import generate_answer
from app.services.document_service import process_document_text
from app.services.search_service import search_chunks
from app.utils.file_utils import save_upload_file, validate_file_upload
from app.utils.logging_config import get_logger
from app.utils.rate_limit import limiter
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

logger = get_logger(__name__)

router = APIRouter()


@router.post("/upload", response_model=UploadResponse, status_code=201)
@limiter.limit("10/hour")
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
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
    db.commit()
    db.refresh(document)  # Get auto-generated ID
    logger.info(f"Upload complete: document_id={document.id}")

    return UploadResponse(
        id=document.id,
        user_id=current_user.id,
        filename=document.filename,
        file_size=document.file_size,
        status=document.status,
        message="File uploaded successfully. Processing will begin shortly.",
    )


@router.get("/", response_model=DocumentListResponse)
@limiter.limit("10/hour")
def get_documents(
    request: Request,
    db: Session = Depends(get_db),
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
    documents = db.scalars(stmt).all()

    return DocumentListResponse(
        documents=[DocumentResponse.model_validate(d) for d in documents],
        total=len(documents),
    )


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(
    document_id: int,
    db: Session = Depends(get_db),
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
    document = db.scalar(stmt)

    if not document:
        raise HTTPException(
            status_code=404, detail=f"Document with ID {document_id} not found"
        )

    return document


@router.delete("/{document_id}")
def delete_document(
    document_id: int,
    db: Session = Depends(get_db),
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
    document = db.scalar(stmt)

    if not document:
        raise HTTPException(
            status_code=404, detail=f"Document with ID {document_id} not found"
        )

    # Delete file from disk
    full_path = settings.get_upload_path().parent / document.file_path
    full_path.unlink(missing_ok=True)

    # Delete from database (cascades to chunks)
    db.delete(document)
    db.commit()

    logger.info(f"Successfully deleted document_id={document_id}")
    return {"message": f"Document {document_id} deleted successfully"}


# PROCESS DOCUMENT
@router.post("/{document_id}/process")
@limiter.limit("20/hour")
def process_document(
    request: Request,
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Process a document: extract text and create chunks.

    Document must be in PENDING status.
    """
    logger.info(f"Processing document_id={document_id}")

    stmt = (
        select(Document)
        .where(Document.id == document_id)
        .where(Document.user_id == current_user.id)
    )
    document = db.scalar(stmt)

    if not document:
        raise HTTPException(
            status_code=404, detail=f"Document with ID {document_id} not found"
        )

    try:
        # Call service layer
        process_document_text(document_id, db)

        return {
            "message": f"Document {document_id} processed successfully",
            "document_id": document_id,
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")


@router.post("/{document_id}/search", response_model=SearchResponse)
@limiter.limit("20/hour")
def search_document(
    request: Request,
    search: SearchRequest,
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    stmt = (
        select(Document)
        .where(Document.id == document_id)
        .where(Document.user_id == current_user.id)
    )
    document = db.scalar(stmt)

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
        results = search_chunks(
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
@limiter.limit("20/hour")
def query_document(
    request: Request,
    document_id: int,
    body: QueryRequest,
    db: Session = Depends(get_db),
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
    stmt = (
        select(Document)
        .where(Document.id == document_id)
        .where(Document.user_id == current_user.id)
    )
    document = db.scalar(stmt)

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
        db.flush()

        # Perform RAG search and generate answer
        search_results = search_chunks(
            query=body.query, document_id=document_id, top_k=5, db=db
        )

        answer = generate_answer(query=body.query, chunks=search_results)

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
        db.commit()

        logger.info(
            f"Saved messages for document_id={document_id}: user_msg_id={user_message.id}, assistant_msg_id={assistant_message.id}"
        )

        return QueryResponse(query=body.query, answer=answer, sources=sources)

    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        db.rollback()
        logger.error(f"Query failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.get("/{document_id}/messages", response_model=MessageListResponse)
def get_document_messages(
    document_id: int,
    db: Session = Depends(get_db),
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
    document = db.scalar(stmt)

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # Get messages for this document and user, ordered by creation time
    stmt = (
        select(Message)
        .where(Message.document_id == document_id)
        .where(Message.user_id == current_user.id)
        .order_by(Message.created_at.asc())
    )
    messages = db.scalars(stmt).all()

    return MessageListResponse(
        messages=[MessageResponse.model_validate(msg) for msg in messages],
        total=len(messages),
    )
