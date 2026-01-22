# backend/app/database.py
from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

# Create database engine (connection pool)
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    echo=False,
    pool_size=5,
    max_overflow=10,
)


# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# Base class for models
class Base(DeclarativeBase):
    """
    Base class for all SQLAlchemy models.

    SQLAlchemy 2.0+ uses DeclarativeBase instead of declarative_base().
    Enables proper type checking with Mapped[] annotations.
    """

    pass


def init_db():
    """Initialize database: enable pgvector, create tables."""
    print("🔄 Initializing database...")

    # Enable pgvector extension
    with engine.connect() as conn:
        try:
            result = conn.execute(
                text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
            )
            if result.fetchone() is None:
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                conn.commit()
                print("✅ pgvector extension enabled")
            else:
                print("✅ pgvector extension already enabled")
        except Exception as e:
            print(f"⚠️  Warning: Could not enable pgvector extension: {e}")
            print("   Make sure you're using the ankane/pgvector Docker image")

    # Create all tables
    Base.metadata.create_all(bind=engine)
    print("✅ Database tables created successfully!")


def get_db():
    """FastAPI dependency for database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
