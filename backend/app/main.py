# backend/app/main.py
from app.config import settings
from app.database import init_db
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Create FastAPI application
app = FastAPI(
    title="Document Intelligence API",
    description="AI-powered document Q&A system using RAG",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)


# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Startup Event
@app.on_event("startup")
async def startup_event():
    """Initialize database on application startup."""
    print("\n" + "=" * 60)
    print("Document Intelligence API Starting...")
    print("=" * 60 + "\n")

    init_db()

    print(f"\nUpload directory: {settings.get_upload_path()}")
    print(f"Max file size: {settings.max_file_size / 1024 / 1024:.1f}MB")
    print(f"\nAPI ready at: http://localhost:8000")
    print(f"Docs available at: http://localhost:8000/docs\n")


# Root Endpoint
@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "message": "Document Intelligence API",
        "status": "running",
        "docs": "/docs",
        "version": "1.0.0",
    }


# Health Check
@app.get("/health")
async def health_check():
    """Detailed health check."""
    return {
        "status": "healthy",
        "database": "connected",
        "upload_dir": str(settings.get_upload_path()),
        "max_file_size_mb": settings.max_file_size / 1024 / 1024,
    }


# Future API Routes
# from app.api import documents, search
# app.include_router(documents.router, prefix="/api/documents", tags=["documents"])
# app.include_router(search.router, prefix="/api/search", tags=["search"])
