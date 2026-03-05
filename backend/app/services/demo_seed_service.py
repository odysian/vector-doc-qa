from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.security import get_password_hash
from app.models.base import Chunk, Document, DocumentStatus
from app.models.user import User
from app.utils.logging_config import get_logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)

DEMO_USERNAME = "demo"
DEMO_EMAIL = "demo@quaero.dev"
DEMO_PASSWORD = "demo"
DEMO_FIXTURE_PATH = (
    Path(__file__).resolve().parents[3] / "scripts" / "fixtures" / "demo_seed_data.json"
)


def _load_fixture_payload(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        logger.warning("Demo seed fixture not found at %s; skipping document seeding", path)
        return None

    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Demo seed fixture must be a JSON object")

    documents = payload.get("documents")
    if not isinstance(documents, list):
        raise ValueError("Demo seed fixture must include a 'documents' list")

    return payload


async def seed_demo_user(db: AsyncSession) -> None:
    """Seed the demo user and fixture-backed documents if the demo user is absent."""
    existing_demo = await db.scalar(select(User.id).where(User.username == DEMO_USERNAME))
    if existing_demo is not None:
        logger.info("Demo user already exists; skipping seed")
        return

    try:
        demo_user = User(
            username=DEMO_USERNAME,
            email=DEMO_EMAIL,
            hashed_password=get_password_hash(DEMO_PASSWORD),
            is_demo=True,
        )
        db.add(demo_user)
        await db.flush()

        payload = _load_fixture_payload(DEMO_FIXTURE_PATH)
        documents_payload = payload.get("documents", []) if payload else []

        for doc_payload in documents_payload:
            if not isinstance(doc_payload, dict):
                continue

            document = Document(
                filename=str(doc_payload.get("filename", "demo-document.pdf")),
                file_path=str(doc_payload.get("file_path", "")),
                file_size=int(doc_payload.get("file_size", 0)),
                status=DocumentStatus.COMPLETED,
                user_id=demo_user.id,
                processed_at=datetime.utcnow(),
                error_message=None,
            )
            db.add(document)
            await db.flush()

            chunks_payload = doc_payload.get("chunks", [])
            if not isinstance(chunks_payload, list):
                continue

            for chunk_payload in chunks_payload:
                if not isinstance(chunk_payload, dict):
                    continue

                raw_embedding = chunk_payload.get("embedding", [])
                embedding = (
                    [float(value) for value in raw_embedding]
                    if isinstance(raw_embedding, list)
                    else []
                )

                db.add(
                    Chunk(
                        document_id=document.id,
                        content=str(chunk_payload.get("content", "")),
                        chunk_index=int(chunk_payload.get("chunk_index", 0)),
                        page_start=None,
                        page_end=None,
                        embedding=embedding,
                    )
                )

        await db.commit()
        logger.info("Demo seed complete: user_id=%s, documents=%s", demo_user.id, len(documents_payload))

    except Exception:
        await db.rollback()
        logger.exception("Demo seed failed")
        raise
