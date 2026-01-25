from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import Chunk, Document, DocumentStatus
from app.schemas.document import DocumentListResponse, DocumentResponse, UploadResponse
from app.schemas.search import SearchRequest, SearchResponse, SearchResult
from app.services.document_service import process_document_text
from app.services.search_service import search_chunks
from app.utils.file_utils import save_upload_file, validate_file_upload
from app.utils.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.post("/upload", response_model=UploadResponse, status_code=201)
async def upload_document(file: UploadFile = File(...), db: Session = Depends(get_db)):
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
    )

    db.add(document)
    db.commit()
    db.refresh(document)  # Get auto-generated ID
    logger.info(f"Upload complete: document_id={document.id}")

    return UploadResponse(
        id=document.id,
        filename=document.filename,
        file_size=document.file_size,
        status=document.status,
        message="File uploaded successfully. Processing will begin shortly.",
    )


@router.get("/", response_model=DocumentListResponse)
def get_documents(db: Session = Depends(get_db)):
    """
    Get all uploaded documents.
    """
    stmt = select(Document).order_by(Document.uploaded_at.desc())
    documents = db.scalars(stmt).all()

    return DocumentListResponse(
        documents=[DocumentResponse.model_validate(d) for d in documents],
        total=len(documents),
    )


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(document_id: int, db: Session = Depends(get_db)):
    """
    Get a specific document by ID.
    """
    stmt = select(Document).where(Document.id == document_id)
    document = db.scalar(stmt)

    if not document:
        raise HTTPException(
            status_code=404, detail=f"Document with ID {document_id} not found"
        )

    return document


@router.delete("/{document_id}")
def delete_document(document_id: int, db: Session = Depends(get_db)):
    """
    Delete a document and its file.
    """
    logger.info(f"Deleting document_id={document_id}")

    stmt = select(Document).where(Document.id == document_id)
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
def process_document(document_id: int, db: Session = Depends(get_db)):
    """
    Process a document: extract text and create chunks.

    Document must be in PENDING status.
    """
    logger.info(f"Processing document_id={document_id}")
    try:
        # Call service layer
        process_document_text(document_id, db)

        return {
            "message": f"Document {document_id} processed successfully",
            "document_id": document_id,
        }

    except ValueError as e:
        # Business logic errors
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        # Unexpected errors
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")


@router.post("/{document_id}/search", response_model=SearchResponse)
def search_document(
    search: SearchRequest, document_id: int, db: Session = Depends(get_db)
):

    # Do i need a joined load to get the chunk relationship?
    stmt = select(Document).where(Document.id == document_id)
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
