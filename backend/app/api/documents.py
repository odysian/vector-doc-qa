from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Document, DocumentStatus
from app.schemas.document import DocumentListResponse, DocumentResponse, UploadResponse
from app.utils.file_utils import save_upload_file, validate_file_upload

router = APIRouter()


# UPLOAD ENDPOINT
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
    db.refresh(document)  # Get the ID that was auto-generated

    return UploadResponse(
        id=document.id,  # type: ignore
        filename=document.filename,  # type: ignore
        file_size=document.file_size,  # type: ignore
        status=document.status,  # type: ignore
        message="File uploaded successfully. Processing will begin shortly.",
    )


# GET ALL DOCUMENTS
@router.get("/", response_model=DocumentListResponse)
async def get_documents(db: Session = Depends(get_db)):
    """
    Get all uploaded documents.
    """
    documents = db.query(Document).order_by(Document.uploaded_at.desc()).all()

    return DocumentListResponse(documents=documents, total=len(documents))  # type: ignore


# GET SINGLE DOCUMENT
@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(document_id: int, db: Session = Depends(get_db)):
    """
    Get a specific document by ID.
    """
    document = db.query(Document).filter(Document.id == document_id).first()

    if not document:
        raise HTTPException(
            status_code=404, detail=f"Document with ID {document_id} not found"
        )

    return document


# DELETE DOCUMENT
@router.delete("/{document_id}")
async def delete_document(document_id: int, db: Session = Depends(get_db)):
    """
    Delete a document and its file.
    """
    document = db.query(Document).filter(Document.id == document_id).first()

    if not document:
        raise HTTPException(
            status_code=404, detail=f"Document with ID {document_id} not found"
        )

    # Delete file from disk
    import os

    from app.config import settings

    file_path = settings.get_upload_path().parent / document.file_path

    if file_path.exists():
        os.remove(file_path)  # type: ignore

    # Delete from database (cascades to chunks)
    db.delete(document)
    db.commit()

    return {"message": f"Document {document_id} deleted successfully"}
