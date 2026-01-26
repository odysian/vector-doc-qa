from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api import documents
from app.config import settings
from app.database import init_db
from app.utils.logging_config import get_logger, setup_logging
from app.utils.rate_limit import limiter

setup_logging(log_level="DEBUG")
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan events: startup and shutdown"""
    logger.info("Starting Document Intelligence API")
    init_db()
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


@app.get("/")
def root():
    """Health check endpoint."""
    return {
        "message": "Document Intelligence API",
        "status": "running",
        "docs": "/docs",
        "version": "1.0.0",
    }


@app.get("/health")
def health_check():
    """Detailed health check."""
    return {
        "status": "healthy",
        "database": "connected",
        "upload_dir": str(settings.get_upload_path()),
        "max_file_size_mb": settings.max_file_size / 1024 / 1024,
    }
