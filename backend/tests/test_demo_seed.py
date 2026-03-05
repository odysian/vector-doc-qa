"""Tests for startup demo-account seed behavior."""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import Chunk, Document, DocumentStatus
from app.models.user import User
from app.services import demo_seed_service


def _write_fixture(path: Path) -> None:
    payload = {
        "documents": [
            {
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
        ]
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


class TestDemoSeedService:
    async def test_seed_creates_demo_user_when_missing(
        self,
        db_session: AsyncSession,
        monkeypatch,
        tmp_path: Path,
    ):
        fixture_path = tmp_path / "demo_seed_data.json"
        _write_fixture(fixture_path)
        monkeypatch.setattr(demo_seed_service, "DEMO_FIXTURE_PATH", fixture_path)

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

    async def test_seed_is_idempotent_when_demo_user_exists(
        self,
        db_session: AsyncSession,
        monkeypatch,
        tmp_path: Path,
    ):
        fixture_path = tmp_path / "demo_seed_data.json"
        _write_fixture(fixture_path)
        monkeypatch.setattr(demo_seed_service, "DEMO_FIXTURE_PATH", fixture_path)

        await demo_seed_service.seed_demo_user(db_session)
        await demo_seed_service.seed_demo_user(db_session)

        demo_user_count = await db_session.scalar(
            select(func.count()).select_from(User).where(User.username == demo_seed_service.DEMO_USERNAME)
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
