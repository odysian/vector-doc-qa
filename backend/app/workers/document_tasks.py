from time import perf_counter

from app.database import AsyncSessionLocal
from app.services.document_service import process_document_text
from app.utils.logging_context import reset_job_id, set_job_id
from app.utils.logging_config import get_logger

logger = get_logger(__name__)


async def process_document_task(ctx: dict, document_id: int) -> None:
    """
    ARQ task entrypoint for processing a document.

    Runs outside request context, so it creates its own AsyncSession.
    """
    job_id = str(ctx.get("job_id") or f"doc:{document_id}")
    job_id_token = set_job_id(job_id)
    task_start = perf_counter()

    logger.info(
        "worker.job_started",
        extra={
            "event": "worker.job_started",
            "document_id": document_id,
            "job_id": job_id,
        },
    )

    try:
        async with AsyncSessionLocal() as db:
            try:
                await process_document_text(document_id=document_id, db=db)
                logger.info(
                    "worker.job_completed",
                    extra={
                        "event": "worker.job_completed",
                        "document_id": document_id,
                        "duration_ms": int((perf_counter() - task_start) * 1000),
                    },
                )
            except ValueError:
                # Expected state errors (already completed/already processing/not found).
                logger.warning(
                    "worker.job_failed",
                    extra={
                        "event": "worker.job_failed",
                        "document_id": document_id,
                        "duration_ms": int((perf_counter() - task_start) * 1000),
                        "error_class": "ValueError",
                    },
                )
            except Exception as exc:
                # process_document_text already marks status=FAILED and stores error_message.
                logger.exception(
                    "worker.job_failed",
                    extra={
                        "event": "worker.job_failed",
                        "document_id": document_id,
                        "duration_ms": int((perf_counter() - task_start) * 1000),
                        "error_class": type(exc).__name__,
                    },
                )
    finally:
        reset_job_id(job_id_token)
