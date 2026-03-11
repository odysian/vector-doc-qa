# backend/app/services/document_service.py
from time import perf_counter

from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import EMBEDDING_BATCH_SIZE
from app.models.base import DocumentStatus
from app.repositories.document_repository import (
    create_chunks_for_document,
    delete_chunks_for_document,
    get_document_by_id,
)
from app.services.embedding_service import generate_embeddings_batch
from app.services.storage_service import read_file_bytes
from app.utils.logging_config import get_logger
from app.utils.pdf_utils import (
    chunk_text,
    extract_text_with_page_boundaries_from_pdf_bytes,
)

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

    # Get document
    document = await get_document_by_id(db=db, document_id=document_id)

    if not document:
        logger.error(f"Document not found: document_id={document_id}")
        raise ValueError(f"Document with ID {document_id} not found")

    # Validate status
    if document.status == DocumentStatus.COMPLETED:
        raise ValueError(f"Document {document_id} already processed")

    if document.status == DocumentStatus.PROCESSING:
        raise ValueError(f"Document {document_id} is currently being processed")

    process_start = perf_counter()
    logger.info(
        "document.processing_started",
        extra={
            "event": "document.processing_started",
            "document_id": document_id,
        },
    )

    try:
        document.status = DocumentStatus.PROCESSING
        document.error_message = None
        document.processed_at = None

        # Retry semantics: always rebuild from scratch to avoid duplicate chunks.
        await delete_chunks_for_document(db=db, document_id=document.id)
        await db.commit()

        # Extract text from pdf (CPU-bound, offloaded to process pool)
        logger.info(f"Extracting text from {document.filename}")
        pdf_bytes = await read_file_bytes(document.file_path)
        extracted_pdf = await extract_text_with_page_boundaries_from_pdf_bytes(pdf_bytes)
        logger.info(f"Extracted {len(extracted_pdf.text)} characters")

        if not extracted_pdf.text or not extracted_pdf.text.strip():
            raise ValueError("No text could be extracted from PDF")

        # Break pdf text into chunks (CPU-bound, stays sync)
        logger.info("Chunking text")
        chunks = chunk_text(
            extracted_pdf.text,
            page_boundaries=extracted_pdf.page_boundaries,
        )
        logger.info(f"Created {len(chunks)} chunks")

        chunk_payloads = [
            (chunk.content, chunk.page_start, chunk.page_end) for chunk in chunks
        ]
        chunk_objects = await create_chunks_for_document(
            db=db,
            document_id=document.id,
            chunk_payloads=chunk_payloads,
        )

        # Generate embeddings in bounded batches to keep memory stable for large docs.
        logger.info(f"Generating embeddings for {len(chunks)} chunks")
        for batch_start in range(0, len(chunk_objects), EMBEDDING_BATCH_SIZE):
            batch_end = min(batch_start + EMBEDDING_BATCH_SIZE, len(chunk_objects))
            chunk_batch = chunk_objects[batch_start:batch_end]
            batch_texts = [chunk.content for chunk in chunk_batch]
            embeddings = await generate_embeddings_batch(batch_texts)

            # Guard invariant even when embedding service is mocked/bypassed in tests.
            if len(embeddings) != len(chunk_batch):
                raise ValueError(
                    "Embedding count mismatch: "
                    f"expected {len(chunk_batch)}, got {len(embeddings)}"
                )

            # Assign by index to preserve explicit chunk->embedding alignment.
            for index, chunk in enumerate(chunk_batch):
                chunk.embedding = embeddings[index]

        logger.info("Embeddings generated and assigned successfully")

        document.status = DocumentStatus.COMPLETED
        document.processed_at = func.now()

        await db.commit()

        logger.info(
            "document.processing_completed",
            extra={
                "event": "document.processing_completed",
                "document_id": document_id,
                "chunk_count": len(chunks),
                "duration_ms": int((perf_counter() - process_start) * 1000),
            },
        )

    except Exception as e:
        logger.error(
            "document.processing_failed",
            extra={
                "event": "document.processing_failed",
                "document_id": document_id,
                "duration_ms": int((perf_counter() - process_start) * 1000),
                "error_class": type(e).__name__,
            },
            exc_info=True,
        )

        # Explicitly clear the current unit of work so flushed chunk rows are not committed.
        await db.rollback()

        failed_document = await get_document_by_id(db=db, document_id=document_id)
        if failed_document:
            failed_document.status = DocumentStatus.FAILED
            failed_document.error_message = str(e)
            failed_document.processed_at = None
            await db.commit()
        raise
