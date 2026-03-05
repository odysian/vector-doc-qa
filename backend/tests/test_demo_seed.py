"""Tests for startup demo-account seed behavior."""

from __future__ import annotations

import base64
import json
from pathlib import Path
from unittest.mock import AsyncMock
from uuid import uuid4

from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

import app.main as app_main
from app.core.security import create_access_token
from app.database import get_db
from app.models.base import Chunk, Document, DocumentStatus
from app.models.user import User
from app.services import demo_seed_service


def _write_fixture(path: Path, *, include_file_content: bool = False) -> None:
    document_payload = {
        "filename": "demo-fixture.pdf",
        "file_path": "uploads/demo-fixture.pdf",
        "file_size": 123,
        "status": "completed",
        "chunks": [
            {
                "content": "Demo chunk content",
                "chunk_index": 0,
                "embedding": [0.1] * 1536,
            }
        ],
    }

    if include_file_content:
        document_payload["file_content_base64"] = base64.b64encode(
            b"%PDF-1.4 fixture-bytes"
        ).decode("ascii")

    payload = {"documents": [document_payload]}
    path.write_text(json.dumps(payload), encoding="utf-8")


class TestDemoSeedService:
    async def _run_startup_seed_file_fetch_flow(
        self,
        *,
        db_session: AsyncSession,
        monkeypatch,
        fixture_path: Path,
    ) -> bytes:
        monkeypatch.setattr(demo_seed_service, "DEMO_FIXTURE_PATH", fixture_path)
        monkeypatch.setattr(app_main, "init_db", AsyncMock(return_value=None))
        monkeypatch.setattr(
            app_main,
            "_cleanup_expired_refresh_tokens",
            AsyncMock(return_value=None),
        )

        class _SessionContext:
            def __init__(self, session: AsyncSession):
                self._session = session

            async def __aenter__(self) -> AsyncSession:
                return self._session

            async def __aexit__(self, exc_type, exc, tb) -> bool:  # type: ignore[no-untyped-def]
                return False

        monkeypatch.setattr(
            app_main,
            "AsyncSessionLocal",
            lambda: _SessionContext(db_session),
        )

        async def _override_get_db():
            yield db_session

        app_main.app.dependency_overrides[get_db] = _override_get_db
        app_main.app.state.limiter.enabled = False

        try:
            async with app_main.app.router.lifespan_context(app_main.app):
                demo_user = await db_session.scalar(
                    select(User).where(User.username == demo_seed_service.DEMO_USERNAME)
                )
                assert demo_user is not None

                headers = {
                    "Authorization": (
                        f"Bearer {create_access_token(data={'sub': str(demo_user.id)})}"
                    )
                }

                transport = ASGITransport(app=app_main.app)
                async with AsyncClient(
                    transport=transport,
                    base_url="http://test",
                ) as client:
                    list_response = await client.get("/api/documents/", headers=headers)
                    assert list_response.status_code == 200
                    documents = list_response.json()["documents"]
                    assert len(documents) == 1

                    document_id = int(documents[0]["id"])
                    file_response = await client.get(
                        f"/api/documents/{document_id}/file",
                        headers=headers,
                    )
                    assert file_response.status_code == 200
                    assert file_response.headers["content-type"].startswith(
                        "application/pdf"
                    )
                    return file_response.content
        finally:
            app_main.app.dependency_overrides.clear()
            app_main.app.state.limiter.enabled = True

    async def test_seed_creates_demo_user_when_missing(
        self,
        db_session: AsyncSession,
        monkeypatch,
        tmp_path: Path,
    ):
        fixture_path = tmp_path / "demo_seed_data.json"
        _write_fixture(fixture_path)
        monkeypatch.setattr(demo_seed_service, "DEMO_FIXTURE_PATH", fixture_path)

        mock_read = AsyncMock(side_effect=FileNotFoundError("missing"))
        mock_write = AsyncMock(return_value=None)
        monkeypatch.setattr(demo_seed_service, "read_file_bytes", mock_read)
        monkeypatch.setattr(demo_seed_service, "write_file_bytes", mock_write)

        await demo_seed_service.seed_demo_user(db_session)

        demo_user = await db_session.scalar(
            select(User).where(User.username == demo_seed_service.DEMO_USERNAME)
        )
        assert demo_user is not None
        assert demo_user.is_demo is True
        assert demo_user.email == demo_seed_service.DEMO_EMAIL

        document = await db_session.scalar(
            select(Document).where(Document.user_id == demo_user.id)
        )
        assert document is not None
        assert document.status == DocumentStatus.COMPLETED
        assert document.filename == "demo-fixture.pdf"

        chunk = await db_session.scalar(select(Chunk).where(Chunk.document_id == document.id))
        assert chunk is not None
        assert chunk.chunk_index == 0
        assert chunk.embedding is not None
        assert len(chunk.embedding) == 1536

        mock_write.assert_awaited_once_with(
            "uploads/demo-fixture.pdf",
            demo_seed_service.DEMO_PLACEHOLDER_PDF_BYTES,
            content_type="application/pdf",
        )

    async def test_seed_uses_embedded_file_content_when_available(
        self,
        db_session: AsyncSession,
        monkeypatch,
        tmp_path: Path,
    ):
        fixture_path = tmp_path / "demo_seed_data.json"
        _write_fixture(fixture_path, include_file_content=True)
        monkeypatch.setattr(demo_seed_service, "DEMO_FIXTURE_PATH", fixture_path)

        mock_read = AsyncMock(return_value=b"should-not-read")
        mock_write = AsyncMock(return_value=None)
        monkeypatch.setattr(demo_seed_service, "read_file_bytes", mock_read)
        monkeypatch.setattr(demo_seed_service, "write_file_bytes", mock_write)

        await demo_seed_service.seed_demo_user(db_session)

        mock_read.assert_not_awaited()
        mock_write.assert_awaited_once_with(
            "uploads/demo-fixture.pdf",
            b"%PDF-1.4 fixture-bytes",
            content_type="application/pdf",
        )

    async def test_seed_is_idempotent_when_demo_user_exists(
        self,
        db_session: AsyncSession,
        monkeypatch,
        tmp_path: Path,
    ):
        fixture_path = tmp_path / "demo_seed_data.json"
        _write_fixture(fixture_path)
        monkeypatch.setattr(demo_seed_service, "DEMO_FIXTURE_PATH", fixture_path)
        monkeypatch.setattr(
            demo_seed_service,
            "read_file_bytes",
            AsyncMock(side_effect=FileNotFoundError("missing")),
        )
        monkeypatch.setattr(
            demo_seed_service,
            "write_file_bytes",
            AsyncMock(return_value=None),
        )

        await demo_seed_service.seed_demo_user(db_session)
        await demo_seed_service.seed_demo_user(db_session)

        demo_user_count = await db_session.scalar(
            select(func.count())
            .select_from(User)
            .where(User.username == demo_seed_service.DEMO_USERNAME)
        )
        assert demo_user_count == 1

        demo_user = await db_session.scalar(
            select(User).where(User.username == demo_seed_service.DEMO_USERNAME)
        )
        assert demo_user is not None

        document_count = await db_session.scalar(
            select(func.count())
            .select_from(Document)
            .where(Document.user_id == demo_user.id)
        )
        assert document_count == 1

    async def test_seed_skips_when_demo_email_already_exists(
        self,
        db_session: AsyncSession,
        monkeypatch,
    ):
        existing_user = User(
            username="not_demo",
            email=demo_seed_service.DEMO_EMAIL,
            hashed_password="unused",
            is_demo=False,
        )
        db_session.add(existing_user)
        await db_session.flush()

        mock_write = AsyncMock(return_value=None)
        monkeypatch.setattr(demo_seed_service, "write_file_bytes", mock_write)

        await demo_seed_service.seed_demo_user(db_session)

        demo_user_count = await db_session.scalar(
            select(func.count())
            .select_from(User)
            .where(User.username == demo_seed_service.DEMO_USERNAME)
        )
        assert demo_user_count == 0
        mock_write.assert_not_awaited()

    async def test_seed_handles_integrity_conflict_without_failing_startup(
        self,
        db_session: AsyncSession,
        monkeypatch,
    ):
        async def _raise_integrity(*args, **kwargs):
            raise IntegrityError("INSERT", {}, Exception("duplicate key"))

        monkeypatch.setattr(db_session, "flush", _raise_integrity)

        await demo_seed_service.seed_demo_user(db_session)

        demo_user_count = await db_session.scalar(
            select(func.count())
            .select_from(User)
            .where(User.username == demo_seed_service.DEMO_USERNAME)
        )
        assert demo_user_count == 0

    async def test_seed_skips_documents_when_fixture_missing(
        self,
        db_session: AsyncSession,
        monkeypatch,
        tmp_path: Path,
        caplog,
    ):
        missing_fixture_path = tmp_path / "does-not-exist.json"
        monkeypatch.setattr(demo_seed_service, "DEMO_FIXTURE_PATH", missing_fixture_path)

        with caplog.at_level("WARNING"):
            await demo_seed_service.seed_demo_user(db_session)

        demo_user = await db_session.scalar(
            select(User).where(User.username == demo_seed_service.DEMO_USERNAME)
        )
        assert demo_user is not None
        assert demo_user.is_demo is True

        document_count = await db_session.scalar(
            select(func.count())
            .select_from(Document)
            .where(Document.user_id == demo_user.id)
        )
        assert document_count == 0
        assert "skipping document seeding" in caplog.text.lower()

    async def test_startup_seeded_demo_file_is_fetchable_via_api(
        self,
        db_session: AsyncSession,
        monkeypatch,
        tmp_path: Path,
    ):
        unique_suffix = uuid4().hex[:8]
        fixture_path = tmp_path / "demo_seed_data.json"
        payload = {
            "documents": [
                {
                    "filename": f"startup-seed-{unique_suffix}.pdf",
                    "file_path": f"uploads/startup-seed-{unique_suffix}.pdf",
                    "file_size": 0,
                    "status": "completed",
                    "chunks": [
                        {
                            "content": "Demo startup chunk",
                            "chunk_index": 0,
                            "embedding": [0.1] * 1536,
                        }
                    ],
                }
            ]
        }
        fixture_path.write_text(json.dumps(payload), encoding="utf-8")

        response_bytes = await self._run_startup_seed_file_fetch_flow(
            db_session=db_session,
            monkeypatch=monkeypatch,
            fixture_path=fixture_path,
        )

        assert response_bytes == demo_seed_service.DEMO_PLACEHOLDER_PDF_BYTES

    async def test_startup_seeded_demo_file_returns_embedded_fixture_bytes(
        self,
        db_session: AsyncSession,
        monkeypatch,
        tmp_path: Path,
    ):
        unique_suffix = uuid4().hex[:8]
        embedded_file_bytes = b"%PDF-1.4 embedded-startup-bytes"
        fixture_path = tmp_path / "demo_seed_data_embedded.json"
        payload = {
            "documents": [
                {
                    "filename": f"startup-seed-embedded-{unique_suffix}.pdf",
                    "file_path": f"uploads/startup-seed-embedded-{unique_suffix}.pdf",
                    "file_size": 0,
                    "status": "completed",
                    "file_content_base64": base64.b64encode(embedded_file_bytes).decode(
                        "ascii"
                    ),
                    "chunks": [
                        {
                            "content": "Demo startup embedded chunk",
                            "chunk_index": 0,
                            "embedding": [0.1] * 1536,
                        }
                    ],
                }
            ]
        }
        fixture_path.write_text(json.dumps(payload), encoding="utf-8")

        response_bytes = await self._run_startup_seed_file_fetch_flow(
            db_session=db_session,
            monkeypatch=monkeypatch,
            fixture_path=fixture_path,
        )

        assert response_bytes == embedded_file_bytes
