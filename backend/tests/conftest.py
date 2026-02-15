"""
Test infrastructure for Quaero backend.

Uses a separate 'quaero_test' schema in the same Docker Postgres instance.
Each test runs inside a transaction that rolls back after completion,
keeping tests isolated without recreating tables per test.
"""

import uuid
from collections.abc import Generator
from datetime import datetime
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.security import create_access_token, get_password_hash
from app.database import Base, get_db
from app.main import app
from app.models.base import Chunk, Document, DocumentStatus
from app.models.user import User

# ---------------------------------------------------------------------------
# Test database configuration
# ---------------------------------------------------------------------------

# Include quaero in search_path so the pgvector VECTOR type (installed in quaero schema) is visible
TEST_DATABASE_URL = (
    "postgresql://postgres:postgres@localhost:5434/document_intelligence"
    "?options=-c%20search_path=quaero_test,quaero,public"
)

test_engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


# ---------------------------------------------------------------------------
# Session-scoped: create/drop schema and tables once per test run
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Create the quaero_test schema and all tables before tests, drop after."""
    with test_engine.connect() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS quaero_test"))
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()

    # Temporarily point all models at quaero_test for table creation
    original_schema = Base.metadata.schema
    Base.metadata.schema = "quaero_test"

    # Update schema on each table individually (needed for FKs to resolve)
    for table in Base.metadata.tables.values():
        table.schema = "quaero_test"

    Base.metadata.create_all(bind=test_engine)

    yield

    # Use CASCADE to handle enum types and other dependencies
    with test_engine.connect() as conn:
        conn.execute(text("DROP SCHEMA IF EXISTS quaero_test CASCADE"))
        conn.commit()

    # Restore original schema
    Base.metadata.schema = original_schema
    for table in Base.metadata.tables.values():
        table.schema = original_schema


# ---------------------------------------------------------------------------
# Function-scoped: transaction rollback per test
# ---------------------------------------------------------------------------


@pytest.fixture()
def db_session(setup_test_database: None) -> Generator[Session, None, None]:
    """
    Provide a database session that rolls back after each test.

    Uses nested transactions (SAVEPOINT) so that code under test can call
    commit() without actually persisting data.
    """
    connection = test_engine.connect()
    transaction = connection.begin()

    session = TestSessionLocal(bind=connection)

    # Use begin_nested() so that session.commit() inside the app creates a
    # SAVEPOINT instead of committing the outer transaction
    nested = connection.begin_nested()

    # After each commit inside the test, restart the nested savepoint
    @pytest.fixture(autouse=True)
    def _restart_savepoint():
        pass

    from sqlalchemy import event

    @event.listens_for(session, "after_transaction_end")
    def restart_savepoint(session, transaction_inner):  # type: ignore[no-untyped-def]
        nonlocal nested
        if transaction_inner.nested and not transaction_inner._parent.nested:
            nested = connection.begin_nested()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


# ---------------------------------------------------------------------------
# FastAPI TestClient
# ---------------------------------------------------------------------------


@pytest.fixture()
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """
    FastAPI TestClient with the test database session injected
    and rate limiting disabled.
    """

    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db

    # Disable rate limiting for tests
    app.state.limiter.enabled = False

    with TestClient(app) as tc:
        yield tc

    app.dependency_overrides.clear()
    app.state.limiter.enabled = True


# ---------------------------------------------------------------------------
# User fixtures
# ---------------------------------------------------------------------------

TEST_PASSWORD = "testpass123!"


def _make_user(db_session: Session, username: str | None = None, email: str | None = None) -> User:
    """Helper to create a user directly in the database."""
    suffix = uuid.uuid4().hex[:8]
    user = User(
        username=username or f"testuser_{suffix}",
        email=email or f"test_{suffix}@example.com",
        hashed_password=get_password_hash(TEST_PASSWORD),
    )
    db_session.add(user)
    db_session.flush()
    return user


def _make_auth_headers(user: User) -> dict[str, str]:
    """Helper to create Authorization headers for a user."""
    token = create_access_token(data={"sub": str(user.id)})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def test_user(db_session: Session) -> User:
    """A test user already in the database."""
    return _make_user(db_session)


@pytest.fixture()
def auth_headers(test_user: User) -> dict[str, str]:
    """Authorization headers for test_user."""
    return _make_auth_headers(test_user)


@pytest.fixture()
def second_user(db_session: Session) -> User:
    """A second user for ownership / authorization tests."""
    return _make_user(db_session)


@pytest.fixture()
def second_user_headers(second_user: User) -> dict[str, str]:
    """Authorization headers for second_user."""
    return _make_auth_headers(second_user)


# ---------------------------------------------------------------------------
# Document fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def test_document(db_session: Session, test_user: User) -> Document:
    """A PENDING document owned by test_user (no file on disk)."""
    doc = Document(
        filename="test.pdf",
        file_path="uploads/test.pdf",
        file_size=1024,
        status=DocumentStatus.PENDING,
        user_id=test_user.id,
    )
    db_session.add(doc)
    db_session.flush()
    return doc


@pytest.fixture()
def processed_document(db_session: Session, test_user: User) -> Document:
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
    db_session.flush()

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

    db_session.flush()
    return doc


# ---------------------------------------------------------------------------
# Mock fixtures for external APIs
# ---------------------------------------------------------------------------

FAKE_EMBEDDING = [0.1] * 1536


@pytest.fixture()
def mock_embeddings():
    """Mock OpenAI embedding service functions."""
    with (
        patch(
            "app.services.embedding_service.generate_embedding",
            return_value=FAKE_EMBEDDING,
        ) as mock_single,
        patch(
            "app.services.embedding_service.generate_embeddings_batch",
        ) as mock_batch,
    ):
        # Batch returns one embedding per input text
        mock_batch.side_effect = lambda texts: [FAKE_EMBEDDING] * len(texts)
        yield {"single": mock_single, "batch": mock_batch}


@pytest.fixture()
def mock_anthropic():
    """Mock Anthropic Claude answer generation."""
    with patch(
        "app.services.anthropic_service.generate_answer",
        return_value="This is a test answer based on the document.",
    ) as mock:
        yield mock
