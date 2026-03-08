from urllib.parse import quote

from fastapi import HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import Document, DocumentStatus
from app.models.user import User
from app.schemas.document import (
    DocumentListResponse,
    DocumentResponse,
    DocumentStatusResponse,
    UploadResponse,
)
from app.services.document_service import (
    create_uploaded_document,
    get_user_document,
    list_user_documents,
    remove_document,
)
from app.services.queue_service import enqueue_document_processing
from app.services.storage_service import delete_file, read_file_bytes
from app.utils.file_utils import save_upload_file, validate_file_upload
from app.utils.logging_config import get_logger

logger = get_logger(__name__)


async def _get_document_for_user_or_404(
    *,
    db: AsyncSession,
    document_id: int,
    user_id: int,
) -> Document:
    document = await get_user_document(
        db=db,
        document_id=document_id,
        user_id=user_id,
    )
    if not document:
        raise HTTPException(
            status_code=404,
            detail=f"Document with ID {document_id} not found",
        )
    return document


async def upload_document_command(
    *,
    db: AsyncSession,
    current_user: User,
    file: UploadFile,
) -> UploadResponse:
    if current_user.is_demo:
        raise HTTPException(
            status_code=403,
            detail="Demo account cannot upload documents",
        )

    logger.info("Uploading: %s", file.filename)

    validate_file_upload(file)
    filename = file.filename
    if filename is None:
        raise HTTPException(status_code=400, detail="No filename provided")

    file_path, file_size = await save_upload_file(file)
    document = await create_uploaded_document(
        db=db,
        filename=filename,
        file_path=file_path,
        file_size=file_size,
        user_id=current_user.id,
    )

    try:
        await enqueue_document_processing(document.id)
    except Exception as exc:
        # Surface queue failures while keeping uploaded file metadata visible for retry.
        document.status = DocumentStatus.FAILED
        document.error_message = "Upload succeeded, but queueing failed. Please retry."
        await db.commit()
        logger.error(
            "Queueing failed for document_id=%s: %s",
            document.id,
            exc,
            exc_info=True,
        )
        raise HTTPException(
            status_code=503,
            detail="Document uploaded but could not be queued for processing.",
        )

    logger.info("Upload complete and queued: document_id=%s", document.id)
    return UploadResponse(
        id=document.id,
        user_id=current_user.id,
        filename=document.filename,
        file_size=document.file_size,
        status=document.status,
        message="File uploaded successfully. Processing started in background.",
    )


async def list_documents_command(
    *,
    db: AsyncSession,
    user_id: int,
) -> DocumentListResponse:
    documents = await list_user_documents(db=db, user_id=user_id)
    return DocumentListResponse(
        documents=[DocumentResponse.model_validate(d) for d in documents],
        total=len(documents),
    )


async def get_document_command(
    *,
    db: AsyncSession,
    document_id: int,
    user_id: int,
) -> Document:
    return await _get_document_for_user_or_404(
        db=db,
        document_id=document_id,
        user_id=user_id,
    )


async def get_document_file_command(
    *,
    db: AsyncSession,
    document_id: int,
    user_id: int,
) -> Response:
    document = await _get_document_for_user_or_404(
        db=db,
        document_id=document_id,
        user_id=user_id,
    )

    try:
        pdf_bytes = await read_file_bytes(document.file_path)
    except (FileNotFoundError, OSError):
        raise HTTPException(
            status_code=404,
            detail="Document file not available",
        )

    safe_filename = document.filename.replace('"', "")
    encoded_filename = quote(document.filename)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'inline; filename="{safe_filename}"; '
                f"filename*=UTF-8''{encoded_filename}"
            ),
            "Cache-Control": "private, max-age=3600",
        },
    )


async def get_document_status_command(
    *,
    db: AsyncSession,
    document_id: int,
    user_id: int,
) -> DocumentStatusResponse:
    document = await _get_document_for_user_or_404(
        db=db,
        document_id=document_id,
        user_id=user_id,
    )
    return DocumentStatusResponse(
        id=document.id,
        status=document.status,
        processed_at=document.processed_at,
        error_message=document.error_message,
    )


async def delete_document_command(
    *,
    db: AsyncSession,
    document_id: int,
    current_user: User,
) -> dict[str, str]:
    if current_user.is_demo:
        raise HTTPException(
            status_code=403,
            detail="Demo account cannot delete documents",
        )

    logger.info("Deleting document_id=%s", document_id)
    document = await _get_document_for_user_or_404(
        db=db,
        document_id=document_id,
        user_id=current_user.id,
    )

    await delete_file(document.file_path)
    await remove_document(db=db, document=document)
    await db.commit()

    logger.info("Successfully deleted document_id=%s", document_id)
    return {"message": f"Document {document_id} deleted successfully"}


async def process_document_command(
    *,
    db: AsyncSession,
    document_id: int,
    user_id: int,
) -> dict[str, str | int]:
    logger.info("Queue processing request for document_id=%s", document_id)
    document = await _get_document_for_user_or_404(
        db=db,
        document_id=document_id,
        user_id=user_id,
    )

    if document.status == DocumentStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail=f"Document {document_id} already processed",
        )
    if document.status == DocumentStatus.PROCESSING:
        raise HTTPException(
            status_code=400,
            detail=f"Document {document_id} is currently being processed",
        )
    if document.status == DocumentStatus.FAILED:
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
            "Failed to enqueue document_id=%s: %s",
            document_id,
            exc,
            exc_info=True,
        )
        raise HTTPException(status_code=503, detail="Failed to queue document processing")

    message = (
        f"Document {document_id} processing already queued"
        if not enqueued
        else f"Document {document_id} queued for background processing"
    )
    return {"message": message, "document_id": document_id}
