# backend/app/database.py
from app.config import settings
from app.utils.logging_config import get_logger
from sqlalchemy import MetaData, create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

logger = get_logger(__name__)

# Create database engine connection pool
# Pool tuned for Render PostgreSQL (direct connection, shared across 3 apps):
# - pool_size=3: conservative for shared free-tier Postgres (max 97 connections)
# - max_overflow=5: allows bursts without exhausting connection limit
# - pool_pre_ping: detects dead connections before handing them out
# - pool_recycle=300: refresh connections periodically for connection hygiene
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    echo=False,
    pool_size=3,
    max_overflow=5,
    pool_recycle=300,
)


# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# All Quaero tables live in the "quaero" schema (shared Postgres DB with other apps, isolated by schema)
# Rostra uses "rostra" schema, Faros uses "faros" schema - all in same portfolio-db
metadata = MetaData(schema="quaero")


# Base class for models
class Base(DeclarativeBase):
    """
    Base class for all SQLAlchemy models.

    SQLAlchemy 2.0+ uses DeclarativeBase. Metadata uses schema="quaero"
    for deployment (Render PostgreSQL, shared with other portfolio projects).
    """

    metadata = metadata


def init_db():
    """Initialize database: enable pgvector extension.

    Note: Table creation is handled by Alembic migrations, not here.
    Run 'alembic upgrade head' to apply migrations.
    """
    logger.info("Initializing database...")

    # Enable pgvector extension
    with engine.connect() as conn:
        try:
            result = conn.execute(
                text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
            )
            if result.fetchone() is None:
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                conn.commit()
                logger.info("pgvector extension enabled")
            else:
                logger.info("pgvector extension already enabled")
        except Exception as e:
            logger.info(f"Warning: Could not enable pgvector extension: {e}")
            logger.info("Make sure you're using the ankane/pgvector Docker image")

    logger.info(
        "Database initialization complete. Use 'alembic upgrade head' to apply migrations."
    )


def get_db():
    """FastAPI dependency for database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
