from datetime import datetime, timedelta

from app.config import settings
from app.database import AsyncSessionLocal
from app.models.base import Document, DocumentStatus
from app.utils.logging_config import get_logger
from app.workers.document_tasks import process_document_task
from arq.connections import RedisSettings
from sqlalchemy import select

logger = get_logger(__name__)


async def _reset_stale_processing_documents() -> int:
    """
    Reset documents stuck in PROCESSING after restarts.

    Render free-tier instances can sleep mid-job. On startup, any old PROCESSING
    rows are returned to PENDING so they can be retried.
    """
    cutoff = datetime.utcnow() - timedelta(minutes=settings.arq_stale_processing_minutes)

    async with AsyncSessionLocal() as db:
        stmt = (
            select(Document)
            .where(Document.status == DocumentStatus.PROCESSING)
            .where(Document.uploaded_at < cutoff)
        )
        stale_documents = (await db.scalars(stmt)).all()

        for document in stale_documents:
            document.status = DocumentStatus.PENDING
            document.error_message = (
                "Processing was interrupted during a restart. Ready for retry."
            )

        if stale_documents:
            await db.commit()

    return len(stale_documents)


async def startup(ctx: dict) -> None:
    reset_count = await _reset_stale_processing_documents()
    if reset_count:
        logger.warning(f"Reset {reset_count} stale PROCESSING documents to PENDING")


class WorkerSettings:
    functions = [process_document_task]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    queue_name = settings.arq_queue_name
    poll_delay = settings.arq_poll_delay_seconds
    job_timeout = settings.arq_job_timeout_seconds
    max_jobs = settings.arq_max_jobs
    keep_result = 0
    on_startup = startup
