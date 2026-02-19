"""
Tests for document endpoints: upload, list, get, delete, process.

Covers TESTPLAN.md "Feature: Document Upload", "Document List", "Document Deletion",
and "Document Processing".
"""

import io
from unittest.mock import AsyncMock, patch

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import Document, DocumentStatus
from app.models.user import User


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Minimal valid PDF content (magic bytes + enough structure to extract empty text)
MINIMAL_PDF = b"""%PDF-1.4
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


async def _upload_pdf(client, headers, content=MINIMAL_PDF, filename="test.pdf"):
    """Helper to upload a PDF file."""
    with patch(
        "app.api.documents.enqueue_document_processing",
        new=AsyncMock(return_value=True),
    ):
        return await client.post(
            "/api/documents/upload",
            headers=headers,
            files={"file": (filename, io.BytesIO(content), "application/pdf")},
        )


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------


class TestUpload:
    """POST /api/documents/upload"""

    async def test_upload_pdf_returns_201_with_pending_status(self, client, auth_headers):
        response = await _upload_pdf(client, auth_headers)

        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "pending"
        assert data["filename"] == "test.pdf"
        assert "id" in data

    async def test_upload_enqueues_background_processing(self, client, auth_headers):
        with patch(
            "app.api.documents.enqueue_document_processing",
            new=AsyncMock(return_value=True),
        ) as mock_enqueue:
            response = await client.post(
                "/api/documents/upload",
                headers=auth_headers,
                files={"file": ("test.pdf", io.BytesIO(MINIMAL_PDF), "application/pdf")},
            )

        assert response.status_code == 201
        doc_id = response.json()["id"]
        mock_enqueue.assert_awaited_once_with(doc_id)

    async def test_upload_returns_503_when_queueing_fails(
        self, client, auth_headers, db_session: AsyncSession
    ):
        with patch(
            "app.api.documents.enqueue_document_processing",
            new=AsyncMock(side_effect=RuntimeError("queue unavailable")),
        ):
            response = await client.post(
                "/api/documents/upload",
                headers=auth_headers,
                files={"file": ("test.pdf", io.BytesIO(MINIMAL_PDF), "application/pdf")},
            )

        assert response.status_code == 503
        assert "could not be queued" in response.json()["detail"].lower()

        result = await db_session.execute(
            select(Document).where(Document.filename == "test.pdf")
        )
        saved_document = result.scalar_one()
        assert saved_document.status == DocumentStatus.FAILED
        assert saved_document.error_message is not None

    async def test_upload_saves_document_record_with_correct_fields(
        self, client, auth_headers, test_user: User, db_session: AsyncSession
    ):
        response = await _upload_pdf(client, auth_headers)
        doc_id = response.json()["id"]

        result = await db_session.execute(
            select(Document).where(Document.id == doc_id)
        )
        doc = result.scalar_one()

        assert doc.user_id == test_user.id
        assert doc.filename == "test.pdf"
        assert doc.file_size > 0
        assert doc.status == DocumentStatus.PENDING

    async def test_upload_returns_401_without_auth(self, client):
        response = await _upload_pdf(client, headers={})
        assert response.status_code == 401

    async def test_upload_returns_400_for_non_pdf_extension(self, client, auth_headers):
        response = await client.post(
            "/api/documents/upload",
            headers=auth_headers,
            files={"file": ("test.txt", io.BytesIO(b"hello"), "text/plain")},
        )
        assert response.status_code == 400
        assert "not allowed" in response.json()["detail"]

    async def test_upload_returns_400_for_fake_pdf_wrong_magic_bytes(self, client, auth_headers):
        """A .pdf file with non-PDF content should be rejected by magic byte check."""
        fake_pdf = b"This is not a real PDF file content"
        response = await _upload_pdf(client, auth_headers, content=fake_pdf)
        assert response.status_code == 400
        assert "does not match PDF format" in response.json()["detail"]


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------


class TestListDocuments:
    """GET /api/documents/"""

    async def test_list_documents_returns_only_own_documents(
        self, client, auth_headers, test_document, second_user, db_session
    ):
        # Create a document for the second user
        other_doc = Document(
            filename="other.pdf",
            file_path="uploads/other.pdf",
            file_size=512,
            status=DocumentStatus.PENDING,
            user_id=second_user.id,
        )
        db_session.add(other_doc)
        await db_session.flush()

        response = await client.get("/api/documents/", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["documents"][0]["id"] == test_document.id

    async def test_list_documents_returns_empty_for_new_user(self, client, second_user_headers):
        response = await client.get("/api/documents/", headers=second_user_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["documents"] == []


# ---------------------------------------------------------------------------
# Get single
# ---------------------------------------------------------------------------


class TestGetDocument:
    """GET /api/documents/{id}"""

    async def test_get_document_returns_own_document(self, client, auth_headers, test_document):
        response = await client.get(f"/api/documents/{test_document.id}", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == test_document.id
        assert data["filename"] == test_document.filename

    async def test_get_document_returns_404_for_other_users_document(
        self, client, second_user_headers, test_document
    ):
        response = await client.get(
            f"/api/documents/{test_document.id}", headers=second_user_headers
        )
        assert response.status_code == 404

    async def test_get_document_returns_404_for_nonexistent_id(self, client, auth_headers):
        response = await client.get("/api/documents/99999", headers=auth_headers)
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


class TestDeleteDocument:
    """DELETE /api/documents/{id}"""

    async def test_delete_document_returns_200(
        self, client, auth_headers, test_document, db_session
    ):
        # Patch the file path resolution so delete doesn't error on missing file
        with patch.object(
            type(test_document),
            "file_path",
            new_callable=lambda: property(lambda self: "uploads/nonexistent.pdf"),
        ):
            response = await client.delete(
                f"/api/documents/{test_document.id}", headers=auth_headers
            )

        assert response.status_code == 200
        assert "deleted" in response.json()["message"].lower()

    async def test_delete_document_returns_404_for_other_users_document(
        self, client, second_user_headers, test_document
    ):
        response = await client.delete(
            f"/api/documents/{test_document.id}", headers=second_user_headers
        )
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Process
# ---------------------------------------------------------------------------


class TestProcessDocument:
    """POST /api/documents/{id}/process"""

    async def test_process_pending_document_returns_202_and_enqueues(
        self, client, auth_headers, test_document
    ):
        with patch(
            "app.api.documents.enqueue_document_processing",
            new=AsyncMock(return_value=True),
        ) as mock_enqueue:
            response = await client.post(
                f"/api/documents/{test_document.id}/process",
                headers=auth_headers,
            )

        assert response.status_code == 202
        assert "queued" in response.json()["message"].lower()
        mock_enqueue.assert_awaited_once_with(test_document.id)

    async def test_process_returns_400_for_already_completed_document(
        self, client, auth_headers, processed_document
    ):
        response = await client.post(
            f"/api/documents/{processed_document.id}/process", headers=auth_headers
        )
        assert response.status_code == 400
        assert "already processed" in response.json()["detail"]

    async def test_process_returns_400_for_processing_document(
        self, client, auth_headers, db_session, test_user
    ):
        processing_doc = Document(
            filename="processing.pdf",
            file_path="uploads/processing.pdf",
            file_size=123,
            status=DocumentStatus.PROCESSING,
            user_id=test_user.id,
        )
        db_session.add(processing_doc)
        await db_session.flush()

        response = await client.post(
            f"/api/documents/{processing_doc.id}/process",
            headers=auth_headers,
        )

        assert response.status_code == 400
        assert "currently being processed" in response.json()["detail"]

    async def test_process_failed_document_resets_and_requeues(
        self, client, auth_headers, db_session, test_user
    ):
        failed_doc = Document(
            filename="failed.pdf",
            file_path="uploads/failed.pdf",
            file_size=123,
            status=DocumentStatus.FAILED,
            user_id=test_user.id,
            error_message="Old error",
        )
        db_session.add(failed_doc)
        await db_session.flush()

        with patch(
            "app.api.documents.enqueue_document_processing",
            new=AsyncMock(return_value=True),
        ):
            response = await client.post(
                f"/api/documents/{failed_doc.id}/process",
                headers=auth_headers,
            )

        assert response.status_code == 202
        await db_session.refresh(failed_doc)
        assert failed_doc.status == DocumentStatus.PENDING
        assert failed_doc.error_message is None

    async def test_process_returns_503_when_queueing_fails(
        self, client, auth_headers, db_session, test_document
    ):
        with patch(
            "app.api.documents.enqueue_document_processing",
            new=AsyncMock(side_effect=RuntimeError("queue unavailable")),
        ):
            response = await client.post(
                f"/api/documents/{test_document.id}/process",
                headers=auth_headers,
            )

        assert response.status_code == 503
        await db_session.refresh(test_document)
        assert test_document.status == DocumentStatus.FAILED
        assert test_document.error_message is not None

    async def test_process_returns_404_for_other_users_document(
        self, client, second_user_headers, test_document
    ):
        response = await client.post(
            f"/api/documents/{test_document.id}/process", headers=second_user_headers
        )
        assert response.status_code == 404


class TestDocumentStatus:
    """GET /api/documents/{id}/status"""

    async def test_get_status_returns_document_status(self, client, auth_headers, test_document):
        response = await client.get(
            f"/api/documents/{test_document.id}/status",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == test_document.id
        assert data["status"] == "pending"

    async def test_get_status_returns_404_for_other_users_document(
        self, client, second_user_headers, test_document
    ):
        response = await client.get(
            f"/api/documents/{test_document.id}/status",
            headers=second_user_headers,
        )
        assert response.status_code == 404
