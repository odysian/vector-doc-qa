from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app.models.base import Chunk, Document, DocumentStatus
from app.services.document_service import process_document_text
from app.utils.pdf_utils import ChunkWithPage, ExtractedPdfText


async def _create_document(
    db_session, user_id: int, *, status: DocumentStatus
) -> Document:
    document = Document(
        filename="service-test.pdf",
        file_path="uploads/service-test.pdf",
        file_size=1234,
        status=status,
        user_id=user_id,
    )
    db_session.add(document)
    await db_session.flush()
    return document


class TestDocumentServiceProcessingIntegrity:
    async def test_failure_after_flush_rolls_back_partial_chunks(
        self, db_session, test_user
    ):
        document = await _create_document(
            db_session, test_user.id, status=DocumentStatus.PENDING
        )

        with (
            patch(
                "app.services.document_service.read_file_bytes",
                new=AsyncMock(return_value=b"%PDF-1.4 test"),
            ),
            patch(
                "app.services.document_service.extract_text_with_page_boundaries_from_pdf_bytes",
                new=AsyncMock(
                    return_value=ExtractedPdfText(
                        text="alpha beta gamma",
                        page_boundaries=[],
                    )
                ),
            ),
            patch(
                "app.services.document_service.chunk_text",
                return_value=[
                    ChunkWithPage(content="chunk-a"),
                    ChunkWithPage(content="chunk-b"),
                ],
            ),
            patch(
                "app.services.document_service.generate_embeddings_batch",
                new=AsyncMock(side_effect=RuntimeError("embedding failure")),
            ),
        ):
            with pytest.raises(RuntimeError, match="embedding failure"):
                await process_document_text(document_id=document.id, db=db_session)

        chunks = (
            await db_session.scalars(
                select(Chunk).where(Chunk.document_id == document.id)
            )
        ).all()
        assert chunks == []

    async def test_failed_status_persists_after_rollback_path(
        self, db_session, test_user
    ):
        document = await _create_document(
            db_session, test_user.id, status=DocumentStatus.PENDING
        )

        with (
            patch(
                "app.services.document_service.read_file_bytes",
                new=AsyncMock(return_value=b"%PDF-1.4 test"),
            ),
            patch(
                "app.services.document_service.extract_text_with_page_boundaries_from_pdf_bytes",
                new=AsyncMock(
                    return_value=ExtractedPdfText(
                        text="alpha beta gamma",
                        page_boundaries=[],
                    )
                ),
            ),
            patch(
                "app.services.document_service.chunk_text",
                return_value=[
                    ChunkWithPage(content="chunk-a"),
                    ChunkWithPage(content="chunk-b"),
                ],
            ),
            patch(
                "app.services.document_service.generate_embeddings_batch",
                new=AsyncMock(side_effect=RuntimeError("embedding failure")),
            ),
        ):
            with pytest.raises(RuntimeError, match="embedding failure"):
                await process_document_text(document_id=document.id, db=db_session)

        await db_session.refresh(document)
        assert document.status == DocumentStatus.FAILED
        assert document.error_message == "embedding failure"
        assert document.processed_at is None

    async def test_retry_rebuilds_single_canonical_chunk_set(
        self, db_session, test_user
    ):
        document = await _create_document(
            db_session, test_user.id, status=DocumentStatus.FAILED
        )
        stale_chunk = Chunk(
            document_id=document.id,
            content="stale chunk from previous attempt",
            chunk_index=0,
            embedding=[0.1] * 1536,
        )
        db_session.add(stale_chunk)
        await db_session.flush()

        # Mirror /process retry behavior: failed doc is reset before worker runs.
        document.status = DocumentStatus.PENDING
        document.error_message = None
        document.processed_at = None
        await db_session.commit()

        with (
            patch(
                "app.services.document_service.read_file_bytes",
                new=AsyncMock(return_value=b"%PDF-1.4 test"),
            ),
            patch(
                "app.services.document_service.extract_text_with_page_boundaries_from_pdf_bytes",
                new=AsyncMock(
                    return_value=ExtractedPdfText(
                        text="new text for retry",
                        page_boundaries=[],
                    )
                ),
            ),
            patch(
                "app.services.document_service.chunk_text",
                return_value=[
                    ChunkWithPage(content="new-chunk-0"),
                    ChunkWithPage(content="new-chunk-1"),
                ],
            ),
            patch(
                "app.services.document_service.generate_embeddings_batch",
                new=AsyncMock(return_value=[[0.2] * 1536, [0.3] * 1536]),
            ),
        ):
            await process_document_text(document_id=document.id, db=db_session)

        await db_session.refresh(document)
        assert document.status == DocumentStatus.COMPLETED
        assert isinstance(document.processed_at, datetime)

        chunks = (
            await db_session.scalars(
                select(Chunk)
                .where(Chunk.document_id == document.id)
                .order_by(Chunk.chunk_index)
            )
        ).all()
        assert len(chunks) == 2
        assert [chunk.chunk_index for chunk in chunks] == [0, 1]
        assert [chunk.content for chunk in chunks] == ["new-chunk-0", "new-chunk-1"]

    async def test_embedding_count_mismatch_fails_with_no_partial_chunk_commit(
        self, db_session, test_user
    ):
        document = await _create_document(
            db_session, test_user.id, status=DocumentStatus.PENDING
        )

        with (
            patch(
                "app.services.document_service.read_file_bytes",
                new=AsyncMock(return_value=b"%PDF-1.4 test"),
            ),
            patch(
                "app.services.document_service.extract_text_with_page_boundaries_from_pdf_bytes",
                new=AsyncMock(
                    return_value=ExtractedPdfText(
                        text="alpha beta gamma",
                        page_boundaries=[],
                    )
                ),
            ),
            patch(
                "app.services.document_service.chunk_text",
                return_value=[
                    ChunkWithPage(content="chunk-a"),
                    ChunkWithPage(content="chunk-b"),
                ],
            ),
            patch(
                "app.services.document_service.generate_embeddings_batch",
                new=AsyncMock(return_value=[[0.2] * 1536]),
            ),
        ):
            with pytest.raises(ValueError, match="Embedding count mismatch"):
                await process_document_text(document_id=document.id, db=db_session)

        chunks = (
            await db_session.scalars(
                select(Chunk).where(Chunk.document_id == document.id)
            )
        ).all()
        assert chunks == []

        await db_session.refresh(document)
        assert document.status == DocumentStatus.FAILED
        assert "Embedding count mismatch" in document.error_message

    async def test_processing_persists_chunk_page_boundaries(
        self, db_session, test_user
    ):
        document = await _create_document(
            db_session, test_user.id, status=DocumentStatus.PENDING
        )

        with (
            patch(
                "app.services.document_service.read_file_bytes",
                new=AsyncMock(return_value=b"%PDF-1.4 test"),
            ),
            patch(
                "app.services.document_service.extract_text_with_page_boundaries_from_pdf_bytes",
                new=AsyncMock(
                    return_value=ExtractedPdfText(
                        text="alpha beta gamma",
                        page_boundaries=[],
                    )
                ),
            ),
            patch(
                "app.services.document_service.chunk_text",
                return_value=[
                    ChunkWithPage(content="chunk-a", page_start=1, page_end=1),
                    ChunkWithPage(content="chunk-b", page_start=1, page_end=2),
                ],
            ),
            patch(
                "app.services.document_service.generate_embeddings_batch",
                new=AsyncMock(return_value=[[0.2] * 1536, [0.3] * 1536]),
            ),
        ):
            await process_document_text(document_id=document.id, db=db_session)

        chunks = (
            await db_session.scalars(
                select(Chunk)
                .where(Chunk.document_id == document.id)
                .order_by(Chunk.chunk_index)
            )
        ).all()

        assert len(chunks) == 2
        assert chunks[0].page_start == 1
        assert chunks[0].page_end == 1
        assert chunks[1].page_start == 1
        assert chunks[1].page_end == 2
