#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.database import AsyncSessionLocal  # noqa: E402
from app.models.base import Document, DocumentStatus  # noqa: E402
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


def _to_serializable_payload(documents: list[Document]) -> dict[str, Any]:
    payload_documents: list[dict[str, Any]] = []
    for document in documents:
        chunks = sorted(document.chunks, key=lambda chunk: chunk.chunk_index)
        payload_documents.append(
            {
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
        )

    return {"documents": payload_documents}


async def _run(user_id: int) -> None:
    async with AsyncSessionLocal() as db:
        documents = await _load_completed_documents(db, user_id)

    payload = _to_serializable_payload(documents)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(f"Wrote {len(documents)} document(s) to {OUTPUT_PATH}")


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
    args = parser.parse_args()

    asyncio.run(_run(user_id=args.user_id))


if __name__ == "__main__":
    main()
