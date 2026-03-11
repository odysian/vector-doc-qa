import asyncio
from typing import TYPE_CHECKING, Any

from app.config import settings
from app.utils.logging_config import get_logger

if TYPE_CHECKING:
    from arq.connections import ArqRedis

logger = get_logger(__name__)

_queue_pool: Any | None = None
_pool_lock = asyncio.Lock()


async def _get_queue_pool() -> "ArqRedis":
    """Create and cache a Redis pool for ARQ enqueue operations."""
    global _queue_pool

    if _queue_pool is not None:
        return _queue_pool

    async with _pool_lock:
        if _queue_pool is None:
            try:
                from arq.connections import RedisSettings, create_pool
            except ModuleNotFoundError as exc:
                raise RuntimeError("ARQ is not installed. Add arq to backend dependencies.") from exc

            redis_settings = RedisSettings.from_dsn(settings.redis_url)
            _queue_pool = await create_pool(redis_settings)
            logger.info("Connected to Redis queue")

    return _queue_pool


async def enqueue_document_processing(document_id: int) -> bool:
    """
    Enqueue document processing in ARQ.

    Returns:
        True if a new job was enqueued.
        False if a job with the same ID already exists.
    """
    job_id = f"doc:{document_id}"

    try:
        pool = await _get_queue_pool()
        job = await pool.enqueue_job(
            "process_document_task",
            document_id,
            _job_id=job_id,
            _queue_name=settings.arq_queue_name,
        )
    except Exception as exc:
        logger.error(
            "document.queue_failed",
            extra={
                "event": "document.queue_failed",
                "document_id": document_id,
                "job_id": job_id,
                "error_class": type(exc).__name__,
            },
            exc_info=True,
        )
        raise

    if job is None:
        logger.info(
            "document.queue_duplicate",
            extra={
                "event": "document.queue_duplicate",
                "document_id": document_id,
                "job_id": job_id,
            },
        )
        return False

    logger.info(
        "document.queue_enqueued",
        extra={
            "event": "document.queue_enqueued",
            "document_id": document_id,
            "job_id": job_id,
        },
    )
    return True
