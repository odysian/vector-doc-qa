"""
Test infrastructure for Quaero backend.

Uses a separate 'quaero_test' schema in the same Docker Postgres instance.
Each test runs inside a transaction that rolls back after completion,
keeping tests isolated without recreating tables per test.
"""

import asyncio
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.security import create_access_token, get_password_hash
from app.database import Base, get_db
from app.main import app
from app.models.base import Chunk, Document, DocumentStatus
from app.models.user import User

# ---------------------------------------------------------------------------
# Test database configuration
# ---------------------------------------------------------------------------

# NullPool avoids connection-reuse issues across different event loops.
# asyncpg uses connect_args for search_path instead of URL params.
test_engine = create_async_engine(
    "postgresql+asyncpg://postgres:postgres@localhost:5434/document_intelligence",
    poolclass=NullPool,
    connect_args={
        "server_settings": {"search_path": "quaero_test,quaero,public"}
    },
)

TestAsyncSession = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# ---------------------------------------------------------------------------
# Session-scoped event loop — ensures all async fixtures share one loop
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def event_loop():
    """Override default event loop to session scope.

    Without this, pytest-asyncio creates a new event loop per test,
    causing 'Future attached to a different loop' errors when
    session-scoped fixtures create connections on one loop and
    function-scoped fixtures try to use them on another.
    """
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ---------------------------------------------------------------------------
# Session-scoped: create/drop schema and tables once per test run
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session", autouse=True)
async def setup_test_database():
    """Create the quaero_test schema and all tables before tests, drop after."""
    async with test_engine.begin() as conn:
        await conn.execute(text("CREATE SCHEMA IF NOT EXISTS quaero_test"))
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

    # Temporarily point all models at quaero_test for table creation
    original_schema = Base.metadata.schema
    Base.metadata.schema = "quaero_test"

    # Update schema on each table individually (needed for FKs to resolve)
    for table in Base.metadata.tables.values():
        table.schema = "quaero_test"

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield

    # Use CASCADE to handle enum types and other dependencies
    async with test_engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA IF EXISTS quaero_test CASCADE"))

    # Restore original schema
    Base.metadata.schema = original_schema
    for table in Base.metadata.tables.values():
        table.schema = original_schema


# ---------------------------------------------------------------------------
# Function-scoped: transaction rollback per test
# ---------------------------------------------------------------------------


@pytest.fixture()
async def db_session(setup_test_database) -> AsyncGenerator[AsyncSession, None]:
    """
    Provide a database session that rolls back after each test.

    Uses nested transactions (SAVEPOINT) so that code under test can call
    commit() without actually persisting data.
    """
    connection = await test_engine.connect()
    transaction = await connection.begin()

    session = TestAsyncSession(bind=connection)

    # Use begin_nested() so that session.commit() inside the app creates a
    # SAVEPOINT instead of committing the outer transaction
    nested = await connection.begin_nested()

    # After each commit inside the test, restart the nested savepoint
    # Event listener goes on sync_session because SQLAlchemy events are sync
    @event.listens_for(session.sync_session, "after_transaction_end")
    def restart_savepoint(session_inner, transaction_inner):  # type: ignore[no-untyped-def]
        nonlocal nested
        if transaction_inner.nested and not transaction_inner._parent.nested:
            nested = connection.sync_connection.begin_nested()

    yield session

    await session.close()
    await transaction.rollback()
    await connection.close()


# ---------------------------------------------------------------------------
# FastAPI AsyncClient
# ---------------------------------------------------------------------------


@pytest.fixture()
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """
    httpx AsyncClient with the test database session injected
    and rate limiting disabled.
    """

    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db

    # Disable rate limiting for tests
    app.state.limiter.enabled = False

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
    app.state.limiter.enabled = True


# ---------------------------------------------------------------------------
# User fixtures
# ---------------------------------------------------------------------------

TEST_PASSWORD = "testpass123!"


async def _make_user(
    db_session: AsyncSession, username: str | None = None, email: str | None = None
) -> User:
    """Helper to create a user directly in the database."""
    suffix = uuid.uuid4().hex[:8]
    user = User(
        username=username or f"testuser_{suffix}",
        email=email or f"test_{suffix}@example.com",
        hashed_password=get_password_hash(TEST_PASSWORD),
    )
    db_session.add(user)
    await db_session.flush()
    return user


def _make_auth_headers(user: User) -> dict[str, str]:
    """Helper to create Authorization headers for a user."""
    token = create_access_token(data={"sub": str(user.id)})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
async def test_user(db_session: AsyncSession) -> User:
    """A test user already in the database."""
    return await _make_user(db_session)


@pytest.fixture()
def auth_headers(test_user: User) -> dict[str, str]:
    """Authorization headers for test_user."""
    return _make_auth_headers(test_user)


@pytest.fixture()
async def second_user(db_session: AsyncSession) -> User:
    """A second user for ownership / authorization tests."""
    return await _make_user(db_session)


@pytest.fixture()
def second_user_headers(second_user: User) -> dict[str, str]:
    """Authorization headers for second_user."""
    return _make_auth_headers(second_user)


# ---------------------------------------------------------------------------
# Document fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
async def test_document(db_session: AsyncSession, test_user: User) -> Document:
    """A PENDING document owned by test_user (no file on disk)."""
    doc = Document(
        filename="test.pdf",
        file_path="uploads/test.pdf",
        file_size=1024,
        status=DocumentStatus.PENDING,
        user_id=test_user.id,
    )
    db_session.add(doc)
    await db_session.flush()
    return doc


@pytest.fixture()
async def processed_document(db_session: AsyncSession, test_user: User) -> Document:
    """
    A COMPLETED document with chunks (fake embeddings) owned by test_user.

    Useful for search, query, and message tests.
    """
    doc = Document(
        filename="processed.pdf",
        file_path="uploads/processed.pdf",
        file_size=2048,
        status=DocumentStatus.COMPLETED,
        user_id=test_user.id,
        processed_at=datetime.utcnow(),
    )
    db_session.add(doc)
    await db_session.flush()

    # Create chunks with fake embeddings (1536 dimensions)
    fake_embedding = [0.1] * 1536
    for i in range(3):
        chunk = Chunk(
            document_id=doc.id,
            content=f"This is test chunk {i} with some content about the document.",
            chunk_index=i,
            embedding=fake_embedding,
        )
        db_session.add(chunk)

    await db_session.flush()
    return doc


# ---------------------------------------------------------------------------
# Mock fixtures for external APIs
# ---------------------------------------------------------------------------

FAKE_EMBEDDING = [0.1] * 1536


@pytest.fixture()
def mock_embeddings():
    """Mock OpenAI embedding service functions (now async)."""
    with (
        patch(
            "app.services.embedding_service.generate_embedding",
            new_callable=AsyncMock,
            return_value=FAKE_EMBEDDING,
        ) as mock_single,
        patch(
            "app.services.embedding_service.generate_embeddings_batch",
            new_callable=AsyncMock,
        ) as mock_batch,
    ):
        # Batch returns one embedding per input text
        mock_batch.side_effect = lambda texts: [FAKE_EMBEDDING] * len(texts)
        yield {"single": mock_single, "batch": mock_batch}


@pytest.fixture()
def mock_anthropic():
    """Mock Anthropic Claude answer generation (now async)."""
    with patch(
        "app.services.anthropic_service.generate_answer",
        new_callable=AsyncMock,
        return_value="This is a test answer based on the document.",
    ) as mock:
        yield mock
