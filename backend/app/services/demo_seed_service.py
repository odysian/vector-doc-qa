"""
Startup demo-account seeding and reconciliation service.

Loads fixture documents, ensures backing files exist, and reconciles the demo
user's DB rows so demo environments stay deterministic across restarts.
"""

from __future__ import annotations

import base64
import binascii
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.security import get_password_hash
from app.models.base import Document
from app.models.user import User
from app.repositories.demo_seed_repository import (
    create_completed_document,
    create_demo_user,
    create_document_chunk,
    delete_documents,
    get_user_by_username_or_email,
    list_documents_with_chunks_for_user,
)
from app.services.storage_service import read_file_bytes, write_file_bytes
from app.utils.logging_config import get_logger
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)

DEMO_USERNAME = "demo"
DEMO_EMAIL = "demo@quaero.dev"
DEMO_PASSWORD = "demo"
DEMO_FIXTURE_PATH = (
    Path(__file__).resolve().parents[2] / "scripts" / "fixtures" / "demo_seed_data.json"
)
DEMO_PLACEHOLDER_PDF_BYTES = b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>
endobj
xref
0 4
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
trailer
<< /Size 4 /Root 1 0 R >>
startxref
190
%%EOF"""


def _coerce_int(value: Any, *, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _coerce_optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


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


def _build_fixture_documents_payload(payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    if payload is None:
        return []

    documents_payload = payload.get("documents", [])
    if not isinstance(documents_payload, list):
        return []

    return [doc for doc in documents_payload if isinstance(doc, dict)]


def _fixture_filename_set(documents_payload: list[dict[str, Any]]) -> set[str]:
    filenames: set[str] = set()
    for index, doc_payload in enumerate(documents_payload, start=1):
        filename = str(doc_payload.get("filename", f"demo-document-{index}.pdf"))
        filenames.add(filename)
    return filenames


def _fixture_document_signature(
    documents_payload: list[dict[str, Any]],
) -> set[tuple[str, int, int]]:
    signature: set[tuple[str, int, int]] = set()
    for index, doc_payload in enumerate(documents_payload, start=1):
        filename = str(doc_payload.get("filename", f"demo-document-{index}.pdf"))
        chunks_payload = doc_payload.get("chunks", [])
        if not isinstance(chunks_payload, list):
            chunks_payload = []

        chunk_count = 0
        chunks_with_page_metadata = 0
        for chunk_payload in chunks_payload:
            if not isinstance(chunk_payload, dict):
                continue
            chunk_count += 1
            page_start = _coerce_optional_int(chunk_payload.get("page_start"))
            page_end = _coerce_optional_int(chunk_payload.get("page_end"))
            if page_start is not None or page_end is not None:
                chunks_with_page_metadata += 1

        signature.add((filename, chunk_count, chunks_with_page_metadata))
    return signature


def _existing_document_signature(existing_documents: list[Document]) -> set[tuple[str, int, int]]:
    signature: set[tuple[str, int, int]] = set()
    for document in existing_documents:
        chunk_count = len(document.chunks)
        chunks_with_page_metadata = sum(
            1
            for chunk in document.chunks
            if chunk.page_start is not None or chunk.page_end is not None
        )
        signature.add((document.filename, chunk_count, chunks_with_page_metadata))
    return signature


async def _ensure_seeded_file(
    *,
    file_path: str,
    filename: str,
    encoded_content: str | None,
) -> int:
    if encoded_content:
        try:
            file_bytes = base64.b64decode(encoded_content, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise ValueError(
                f"Invalid base64 file_content_base64 for demo fixture document '{filename}'"
            ) from exc

        await write_file_bytes(file_path, file_bytes, content_type="application/pdf")
        return len(file_bytes)

    try:
        existing_bytes = await read_file_bytes(file_path)
        return len(existing_bytes)
    except FileNotFoundError:
        pass
    except OSError:
        pass

    await write_file_bytes(
        file_path,
        DEMO_PLACEHOLDER_PDF_BYTES,
        content_type="application/pdf",
    )
    logger.warning(
        "Demo seed source file missing for '%s' at %s; wrote placeholder PDF",
        filename,
        file_path,
    )
    return len(DEMO_PLACEHOLDER_PDF_BYTES)


async def _seed_documents(
    db: AsyncSession,
    *,
    demo_user_id: int,
    documents_payload: list[dict[str, Any]],
) -> None:
    for index, doc_payload in enumerate(documents_payload, start=1):
        filename = str(doc_payload.get("filename", f"demo-document-{index}.pdf"))
        file_path = str(doc_payload.get("file_path", "")).strip()
        if not file_path:
            file_path = f"uploads/demo-seed-{index}.pdf"

        resolved_file_size = await _ensure_seeded_file(
            file_path=file_path,
            filename=filename,
            encoded_content=(
                str(doc_payload.get("file_content_base64"))
                if doc_payload.get("file_content_base64")
                else None
            ),
        )
        fixture_file_size = _coerce_int(doc_payload.get("file_size"), default=0)

        document = await create_completed_document(
            db=db,
            user_id=demo_user_id,
            filename=filename,
            file_path=file_path,
            file_size=fixture_file_size if fixture_file_size > 0 else resolved_file_size,
            processed_at=datetime.utcnow(),
        )

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

            await create_document_chunk(
                db=db,
                document_id=document.id,
                content=str(chunk_payload.get("content", "")),
                chunk_index=_coerce_int(chunk_payload.get("chunk_index"), default=0),
                page_start=_coerce_optional_int(chunk_payload.get("page_start")),
                page_end=_coerce_optional_int(chunk_payload.get("page_end")),
                embedding=embedding,
            )


async def _reconcile_documents_for_existing_demo_user(
    db: AsyncSession,
    *,
    demo_user: User,
    documents_payload: list[dict[str, Any]],
) -> int:
    existing_documents = await list_documents_with_chunks_for_user(
        db=db,
        user_id=demo_user.id,
    )
    fixture_filenames = _fixture_filename_set(documents_payload)
    existing_filenames = {document.filename for document in existing_documents}

    if fixture_filenames == existing_filenames and _fixture_document_signature(
        documents_payload
    ) == _existing_document_signature(existing_documents):
        logger.info("Demo seed no-op: fixture signature unchanged")
        return len(existing_documents)

    await delete_documents(db=db, documents=existing_documents)

    await _seed_documents(db, demo_user_id=demo_user.id, documents_payload=documents_payload)
    logger.info(
        "Demo seed reconciled: deleted=%s, seeded=%s",
        len(existing_documents),
        len(documents_payload),
    )
    return len(documents_payload)


async def seed_demo_user(db: AsyncSession) -> None:
    """Seed or reconcile demo user documents from fixture data on startup."""
    existing_demo = await get_user_by_username_or_email(
        db=db,
        username=DEMO_USERNAME,
        email=DEMO_EMAIL,
    )

    try:
        payload = _load_fixture_payload(DEMO_FIXTURE_PATH)
        if existing_demo is not None and payload is None:
            logger.info(
                "Demo seed reconciliation skipped: fixture missing for existing user"
            )
            return
        documents_payload = _build_fixture_documents_payload(payload)

        if existing_demo is None:
            try:
                demo_user = await create_demo_user(
                    db=db,
                    username=DEMO_USERNAME,
                    email=DEMO_EMAIL,
                    hashed_password=get_password_hash(DEMO_PASSWORD),
                )
            except IntegrityError:
                await db.rollback()
                logger.info("Demo seed skipped due to concurrent unique-key conflict")
                return

            await _seed_documents(
                db,
                demo_user_id=demo_user.id,
                documents_payload=documents_payload,
            )
            seeded_count = len(documents_payload)
        else:
            if not existing_demo.is_demo:
                logger.info("Demo seed skipped: matching user/email exists but is not demo")
                return
            seeded_count = await _reconcile_documents_for_existing_demo_user(
                db,
                demo_user=existing_demo,
                documents_payload=documents_payload,
            )

        await db.commit()
        logger.info(
            "Demo seed complete: user_id=%s, documents=%s",
            (existing_demo.id if existing_demo is not None else demo_user.id),
            seeded_count,
        )

    except Exception:
        await db.rollback()
        logger.exception("Demo seed failed")
        raise
