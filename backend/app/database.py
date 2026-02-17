# backend/app/database.py
from collections.abc import AsyncGenerator

from app.config import settings
from app.utils.logging_config import get_logger
from sqlalchemy import MetaData, create_engine, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Sync engine — kept for Alembic migrations (which run synchronously)
# ---------------------------------------------------------------------------
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    echo=False,
    pool_size=3,
    max_overflow=5,
    pool_recycle=300,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# ---------------------------------------------------------------------------
# Async engine — used by the FastAPI application
# ---------------------------------------------------------------------------
# Pool tuned for Render PostgreSQL (direct connection, shared across 3 apps):
# - pool_size=3: conservative for shared free-tier Postgres (max 97 connections)
# - max_overflow=5: allows bursts without exhausting connection limit
# - pool_pre_ping: detects dead connections before handing them out
# - pool_recycle=300: refresh connections periodically for connection hygiene
#
# connect_args sets search_path because asyncpg doesn't support the
# ?options=-c%20search_path=... URL parameter that psycopg2 uses.
async_engine = create_async_engine(
    settings.async_database_url,
    pool_pre_ping=True,
    echo=False,
    pool_size=3,
    max_overflow=5,
    pool_recycle=300,
    connect_args={"server_settings": {"search_path": "quaero,public"}},
)

# expire_on_commit=False prevents MissingGreenlet errors when accessing
# model attributes after commit in async context
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

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


async def init_db() -> None:
    """Initialize database: enable pgvector extension.

    Note: Table creation is handled by Alembic migrations, not here.
    Run 'alembic upgrade head' to apply migrations.
    """
    logger.info("Initializing database...")

    async with async_engine.begin() as conn:
        try:
            result = await conn.execute(
                text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
            )
            if result.fetchone() is None:
                await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                logger.info("pgvector extension enabled")
            else:
                logger.info("pgvector extension already enabled")
        except Exception as e:
            logger.info(f"Warning: Could not enable pgvector extension: {e}")
            logger.info("Make sure you're using the ankane/pgvector Docker image")

    logger.info(
        "Database initialization complete. Use 'alembic upgrade head' to apply migrations."
    )


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for async database sessions."""
    async with AsyncSessionLocal() as db:
        yield db
