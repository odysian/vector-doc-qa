"""
Tests for document endpoints: upload, list, get, delete, process.

Covers TESTPLAN.md "Feature: Document Upload", "Document List", "Document Deletion",
and "Document Processing".
"""

import io
from unittest.mock import patch

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

    async def test_process_pending_document_sets_status_completed(
        self, client, auth_headers, db_session, test_user, mock_embeddings
    ):
        """Create a real PDF on disk, upload reference it, then process."""
        # Create a PDF with actual extractable text
        pdf_content = b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792]
   /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>
endobj
4 0 obj
<< /Length 44 >>
stream
BT /F1 12 Tf 100 700 Td (Hello World) Tj ET
endstream
endobj
5 0 obj
<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>
endobj
xref
0 6
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000266 00000 n
0000000360 00000 n
trailer
<< /Size 6 /Root 1 0 R >>
startxref
441
%%EOF"""

        # Write PDF to the uploads directory
        from app.config import settings

        upload_dir = settings.get_upload_path()
        pdf_path = upload_dir / "test_process.pdf"
        pdf_path.write_bytes(pdf_content)

        try:
            doc = Document(
                filename="test_process.pdf",
                file_path="uploads/test_process.pdf",
                file_size=len(pdf_content),
                status=DocumentStatus.PENDING,
                user_id=test_user.id,
            )
            db_session.add(doc)
            await db_session.flush()

            response = await client.post(
                f"/api/documents/{doc.id}/process", headers=auth_headers
            )

            assert response.status_code == 200
            assert "processed successfully" in response.json()["message"]

            # Verify document status updated
            await db_session.refresh(doc)
            assert doc.status == DocumentStatus.COMPLETED
        finally:
            pdf_path.unlink(missing_ok=True)

    async def test_process_returns_400_for_already_completed_document(
        self, client, auth_headers, processed_document
    ):
        response = await client.post(
            f"/api/documents/{processed_document.id}/process", headers=auth_headers
        )
        assert response.status_code == 400
        assert "already processed" in response.json()["detail"]

    async def test_process_returns_404_for_other_users_document(
        self, client, second_user_headers, test_document
    ):
        response = await client.post(
            f"/api/documents/{test_document.id}/process", headers=second_user_headers
        )
        assert response.status_code == 404
