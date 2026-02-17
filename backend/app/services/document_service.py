# backend/app/services/document_service.py
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.base import Chunk, Document, DocumentStatus
from app.services.embedding_service import generate_embeddings_batch
from app.utils.logging_config import get_logger
from app.utils.pdf_utils import chunk_text, extract_text_from_pdf

logger = get_logger(__name__)


async def process_document_text(document_id: int, db: AsyncSession) -> None:
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
    stmt = select(Document).where(Document.id == document_id).where()
    document = await db.scalar(stmt)

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
        await db.commit()

        pdf_path = settings.get_upload_path().parent / document.file_path

        # Extract text from pdf (CPU-bound, stays sync)
        logger.info(f"Extracting text from {document.filename}")
        text = extract_text_from_pdf(str(pdf_path))
        logger.info(f"Extracted {len(text)} characters")

        if not text or not text.strip():
            raise ValueError("No text could be extracted from PDF")

        # Break pdf text into chunks (CPU-bound, stays sync)
        logger.info("Chunking text")
        chunks = chunk_text(text)
        logger.info(f"Created {len(chunks)} chunks")

        # Build chunks and add to db, chunk_objects list preserves order for embeddings
        chunk_objects = []
        for i, chunk_content in enumerate(chunks):
            chunk = Chunk(document_id=document.id, content=chunk_content, chunk_index=i)
            chunk_objects.append(chunk)
            db.add(chunk)

        # Flush to get chunk IDs without committing
        await db.flush()

        # Generate embeddings for all chunks (async API call)
        logger.info(f"Generating embeddings for {len(chunks)} chunks")
        chunk_texts = [chunk.content for chunk in chunk_objects]
        embeddings = await generate_embeddings_batch(chunk_texts)

        # Assign embeddings to chunks
        for chunk, embedding in zip(chunk_objects, embeddings):
            chunk.embedding = embedding

        logger.info("Embeddings generated and assigned successfully")

        document.status = DocumentStatus.COMPLETED
        document.processed_at = func.now()

        await db.commit()

        logger.info(f"Processing complete: {len(chunks)} chunks with embeddings")

    except Exception as e:
        logger.error(f"Processing failed: {e}", exc_info=True)
        document.status = DocumentStatus.FAILED
        document.error_message = str(e)
        await db.commit()
        raise
