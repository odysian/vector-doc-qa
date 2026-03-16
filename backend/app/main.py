from contextlib import asynccontextmanager
from time import perf_counter
from uuid import uuid4

from arq.connections import RedisSettings, create_pool
from app.api import auth, documents, workspaces
from app.api.dependencies import csrf_header_for_docs, verify_csrf
from app.config import settings
from app.database import AsyncSessionLocal, async_engine, get_db, init_db
from app.services.demo_seed_service import seed_demo_user
from app.utils.logging_context import reset_request_id, set_request_id
from app.utils.logging_config import get_logger, setup_logging
from app.utils.rate_limit import limiter
from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send
from sqlalchemy import text

setup_logging(
    log_level=settings.log_level,
    enable_file_logging=settings.enable_file_logging,
    log_file_max_bytes=settings.log_file_max_bytes,
    log_file_backup_count=settings.log_file_backup_count,
    service="api",
    app_env=settings.app_env,
    version=settings.app_version,
)
logger = get_logger(__name__)


class RequestContextASGIMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    @staticmethod
    def _resolve_request_id(scope: Scope) -> str:
        for header_name, header_value in scope.get("headers", []):
            if header_name == b"x-request-id":
                candidate = header_value.decode("latin1").strip()
                if candidate:
                    return candidate
        return str(uuid4())

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = self._resolve_request_id(scope)
        scope.setdefault("state", {})["request_id"] = request_id
        request_id_token = set_request_id(request_id)
        start_time = perf_counter()
        status_code = 500
        method = scope.get("method", "UNKNOWN")
        path = scope.get("path", "")

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = int(message["status"])
                headers = MutableHeaders(raw=message["headers"])
                headers["X-Request-ID"] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            logger.info(
                "request.completed",
                extra={
                    "event": "request.completed",
                    "request_id": request_id,
                    "method": method,
                    "path": path,
                    "status_code": status_code,
                    "duration_ms": int((perf_counter() - start_time) * 1000),
                },
            )
            reset_request_id(request_id_token)


async def _cleanup_expired_refresh_tokens() -> None:
    """Delete expired refresh token rows on startup to prevent unbounded table growth."""
    async for db in get_db():
        await db.execute(
            text("DELETE FROM quaero.refresh_tokens WHERE expires_at < now()")
        )
        await db.commit()


async def _seed_demo_account() -> None:
    """Seed the demo account and optional fixture-backed data."""
    async with AsyncSessionLocal() as db:
        await seed_demo_user(db)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan events: startup and shutdown"""
    logger.info("Starting Document Intelligence API")
    await init_db()
    await _seed_demo_account()
    await _cleanup_expired_refresh_tokens()
    logger.info("API ready")
    yield

    logger.info("Shutting down")


app = FastAPI(
    title="Document Intelligence API",
    description="AI-powered document Q&A system using RAG",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
    swagger_ui_parameters={"persistAuthorization": True},
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["Content-Type", "Authorization", "X-CSRF-Token", "X-Request-ID"],
    expose_headers=["X-Request-ID"],
)
app.add_middleware(RequestContextASGIMiddleware)


@app.exception_handler(Exception)
async def unhandled_exception_response(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", None) or request.headers.get(
        "X-Request-ID"
    )
    if request_id is None:
        request_id = str(uuid4())
    logger.exception(
        "request.unhandled_exception",
        extra={
            "event": "request.unhandled_exception",
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
        },
        exc_info=exc,
    )
    return PlainTextResponse(
        "Internal Server Error",
        status_code=500,
        headers={"X-Request-ID": request_id},
    )


app.include_router(
    documents.router,
    prefix="/api/documents",
    tags=["documents"],
    dependencies=[Depends(csrf_header_for_docs), Depends(verify_csrf)],
)
app.include_router(
    workspaces.router,
    prefix="/api/workspaces",
    tags=["workspaces"],
    dependencies=[Depends(csrf_header_for_docs), Depends(verify_csrf)],
)
app.include_router(
    auth.router,
    prefix="/api/auth",
    tags=["auth"],
    dependencies=[Depends(csrf_header_for_docs), Depends(verify_csrf)],
)


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "message": "Document Intelligence API",
        "status": "running",
        "docs": "/docs",
        "version": "1.0.0",
    }


@app.get("/health")
async def health_check():
    """Detailed health check."""
    db_status = "disconnected"
    redis_status = "disconnected"
    redis_pool = None

    try:
        async with async_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception:
        logger.warning("Health check: database unreachable")

    try:
        redis_pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
        await redis_pool.ping()
        redis_status = "connected"
    except Exception:
        logger.warning("Health check: Redis unreachable")
    finally:
        if redis_pool is not None:
            await redis_pool.close()

    if db_status == "connected" and redis_status == "connected":
        return {"status": "healthy", "database": db_status, "redis": redis_status}

    if db_status == "connected":
        return JSONResponse(
            status_code=503,
            content={
                "status": "degraded",
                "database": db_status,
                "redis": redis_status,
            },
        )

    return JSONResponse(
        status_code=503,
        content={
            "status": "unhealthy",
            "database": db_status,
            "redis": redis_status,
        },
    )
