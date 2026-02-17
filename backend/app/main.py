from contextlib import asynccontextmanager

from app.api import auth, documents
from app.config import settings
from app.database import async_engine, init_db
from app.utils.logging_config import get_logger, setup_logging
from app.utils.rate_limit import limiter
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text

setup_logging(log_level="DEBUG")
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan events: startup and shutdown"""
    logger.info("Starting Document Intelligence API")
    await init_db()
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
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(documents.router, prefix="/api/documents", tags=["documents"])
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])


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

    async def _check_database() -> bool:
        """Return True if database is reachable, False otherwise."""
        try:
            async with async_engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return True
        except Exception:
            return False

    if await _check_database():
        return {
            "status": "healthy",
            "database": "connected",
            "upload_dir": str(settings.get_upload_path()),
            "max_file_size_mb": settings.max_file_size / 1024 / 1024,
        }
    else:
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "database": "error",
                "upload_dir": str(settings.get_upload_path()),
                "max_file_size_mb": settings.max_file_size / 1024 / 1024,
            },
        )
