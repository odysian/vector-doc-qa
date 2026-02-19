from app.database import AsyncSessionLocal
from app.services.document_service import process_document_text
from app.utils.logging_config import get_logger

logger = get_logger(__name__)


async def process_document_task(ctx: dict, document_id: int) -> None:
    """
    ARQ task entrypoint for processing a document.

    Runs outside request context, so it creates its own AsyncSession.
    """
    logger.info(f"Worker processing document_id={document_id}")

    async with AsyncSessionLocal() as db:
        try:
            await process_document_text(document_id=document_id, db=db)
        except ValueError as exc:
            # Expected state errors (already completed/already processing/not found).
            logger.info(f"Skipping document_id={document_id}: {exc}")
        except Exception:
            # process_document_text already marks status=FAILED and stores error_message.
            logger.exception(
                f"Unhandled worker failure for document_id={document_id}"
            )
