# backend/app/services/document_service.py
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Chunk, Document, DocumentStatus
from app.utils.logging_config import get_logger
from app.utils.pdf_utils import chunk_text, extract_text_from_pdf

logger = get_logger(__name__)


def process_document_text(document_id: int, db: Session) -> None:
    """
    Process a document: extract text, chunk it, save to database.

    Args:
        document_id: ID of document to process
        db: Database session

    Raises:
        ValueError: If document not found or cannot be processed
        Exception: If processing fails
    """

    logger.info(f"Starting document processing: document_id={document_id}")

    # Get document
    stmt = select(Document).where(Document.id == document_id)
    document = db.scalar(stmt)

    if not document:
        logger.error(f"Document not found: document_id={document_id}")
        raise ValueError(f"Document with ID {document_id} not found")

    # Validate status
    if document.status == DocumentStatus.COMPLETED:
        raise ValueError(f"Document {document_id} already processed")

    if document.status == DocumentStatus.PROCESSING:
        raise ValueError(f"Document {document_id} is currently being processed")

    try:
        document.status = DocumentStatus.PROCESSING
        db.commit()

        pdf_path = settings.get_upload_path().parent / document.file_path

        logger.info(f"Extracting text from {document.filename}")
        text = extract_text_from_pdf(str(pdf_path))
        logger.info(f"Extracted {len(text)} characters")

        if not text or not text.strip():
            raise ValueError("No text could be extracted from PDF")

        logger.info(f"Chunking text")
        chunks = chunk_text(text)
        logger.info(f"Created {len(chunks)} chunks")

        for i, chunk_content in enumerate(chunks):
            chunk = Chunk(document_id=document.id, content=chunk_content, chunk_index=i)
            db.add(chunk)

        document.status = DocumentStatus.COMPLETED
        document.processed_at = func.now()

        db.commit()

        logger.info(f"Processing complete: {len(chunks)} chunks")

    except Exception as e:
        logger.error(f"Processing failed: {e}", exc_info=True)
        document.status = DocumentStatus.FAILED
        document.error_message = str(e)
        db.commit()
        raise
