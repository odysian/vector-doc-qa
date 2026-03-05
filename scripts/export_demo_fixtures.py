#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import base64
import json
import sys
from pathlib import Path
from typing import Any

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.database import AsyncSessionLocal  # noqa: E402
from app.models.base import Document, DocumentStatus  # noqa: E402
from app.services.storage_service import read_file_bytes  # noqa: E402
from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402
from sqlalchemy.orm import selectinload  # noqa: E402

OUTPUT_PATH = Path(__file__).resolve().parent / "fixtures" / "demo_seed_data.json"


async def _load_completed_documents(db: AsyncSession, user_id: int) -> list[Document]:
    stmt = (
        select(Document)
        .where(
            Document.user_id == user_id,
            Document.status == DocumentStatus.COMPLETED,
        )
        .options(selectinload(Document.chunks))
        .order_by(Document.id.asc())
    )
    return list((await db.scalars(stmt)).unique().all())


async def _to_serializable_payload(
    documents: list[Document], *, include_file_bytes: bool
) -> tuple[dict[str, Any], int]:
    payload_documents: list[dict[str, Any]] = []
    missing_files = 0

    for document in documents:
        chunks = sorted(document.chunks, key=lambda chunk: chunk.chunk_index)
        payload_document: dict[str, Any] = {
            "filename": document.filename,
            "file_path": document.file_path,
            "file_size": document.file_size,
            "status": DocumentStatus.COMPLETED.value,
            "chunks": [
                {
                    "content": chunk.content,
                    "chunk_index": chunk.chunk_index,
                    "embedding": (
                        [float(value) for value in chunk.embedding]
                        if chunk.embedding is not None
                        else []
                    ),
                }
                for chunk in chunks
            ],
        }

        if include_file_bytes:
            try:
                file_bytes = await read_file_bytes(document.file_path)
                payload_document["file_content_base64"] = base64.b64encode(file_bytes).decode(
                    "ascii"
                )
            except (FileNotFoundError, OSError):
                missing_files += 1

        payload_documents.append(payload_document)

    return {"documents": payload_documents}, missing_files


async def _run(user_id: int, *, include_file_bytes: bool) -> None:
    async with AsyncSessionLocal() as db:
        documents = await _load_completed_documents(db, user_id)

    payload, missing_files = await _to_serializable_payload(
        documents,
        include_file_bytes=include_file_bytes,
    )
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )

    print(f"Wrote {len(documents)} document(s) to {OUTPUT_PATH}")
    if include_file_bytes:
        print(f"Embedded file bytes for {len(documents) - missing_files} document(s)")
    if missing_files > 0:
        print(f"Warning: {missing_files} document source file(s) were missing in storage")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export completed documents/chunks for demo seed fixtures",
    )
    parser.add_argument(
        "--user-id",
        type=int,
        required=True,
        help="User ID to export completed documents from",
    )
    parser.add_argument(
        "--include-file-bytes",
        action="store_true",
        help=(
            "Embed base64 PDF bytes into fixture JSON so seeded demo docs can"
            " render original files in fresh environments"
        ),
    )
    args = parser.parse_args()

    asyncio.run(
        _run(
            user_id=args.user_id,
            include_file_bytes=args.include_file_bytes,
        )
    )


if __name__ == "__main__":
    main()
