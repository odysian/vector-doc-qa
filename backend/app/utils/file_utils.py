import secrets
import tempfile
from datetime import datetime
from pathlib import Path

from app.config import settings
from app.constants import PDF_MAGIC_BYTES, UPLOAD_CHUNK_SIZE_BYTES
from app.services.storage_service import write_file_from_path
from fastapi import HTTPException, UploadFile


# File Validation
def validate_file_upload(file: UploadFile) -> None:
    """
    Validate uploaded file for security and correctness.

    Checks:
    1. File has a filename
    2. File extension is allowed (.pdf)
    3. File size is within limit

    Note: Content (magic-byte) validation is done in save_upload_file to avoid
    consuming the stream here. Extension-only checks do not block malware
    disguised as PDFs; magic bytes do.
    Raises HTTPException if validation fails.
    """

    # File must have filename
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    # File extension must be allowed
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in settings.allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"File type {file_ext} not allowed. Allowed types: {', '.join(settings.allowed_extensions)}",
        )

    # File size must be within limit
    if file.size and file.size > settings.max_file_size:
        max_mb = settings.max_file_size / 1024 / 1024
        raise HTTPException(
            status_code=413, detail=f"File too large. Maximum size: {max_mb}MB"
        )


def generate_unique_filename(original_filename: str) -> str:
    """
    Generate a unique filename to prevent conflicts and path traversal attacks.

    Format: YYYY-MM-DD_RANDOM_original_name.pdf

    Security:
    - Sanitizes filename
    - Adds random component
    - Adds timestamp for sorting
    """

    path = Path(original_filename)
    ext = path.suffix.lower()  # .pdf
    name = path.stem  # filename without extension

    # Sanitize filename: only alphanum, dash, underscore
    # Prevents path traversal: ../../etc/passwd becomes etc_passwd
    safe_name = "".join(c if c.isalnum() or c in ["-", "_"] else "_" for c in name)

    # Limit filename length
    safe_name = safe_name[:100]

    # Generate unique components
    timestamp = datetime.now().strftime("%Y-%m-%d")
    random_str = secrets.token_hex(4)

    # Combine
    unique_filename = f"{timestamp}_{random_str}_{safe_name}{ext}"

    return unique_filename


# File Storage
async def save_upload_file(file: UploadFile) -> tuple[str, int]:
    """
    Save uploaded file through the configured storage backend.

    Returns:
        tuple: (file_path, file_size)

    Security:
    - Validates file content during read
    - Uses unique filename
    - Enforces max size before persisting
    """

    unique_filename = generate_unique_filename(file.filename)  # type: ignore

    # Read upload stream in chunks, validate, and spool to a temp file.
    file_size = 0
    chunk_size = UPLOAD_CHUNK_SIZE_BYTES  # 1MB chunks
    first_chunk = True
    is_pdf = unique_filename.lower().endswith(".pdf")
    temp_path: str | None = None

    try:
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_path = temp_file.name

            while chunk := await file.read(chunk_size):
                # Reject non-PDF content when extension is .pdf (blocks malware renamed as .pdf)
                if first_chunk and is_pdf and not chunk.startswith(PDF_MAGIC_BYTES):
                    raise HTTPException(
                        status_code=400,
                        detail="File content does not match PDF format. Only real PDF files are allowed.",
                    )
                first_chunk = False

                file_size += len(chunk)

                # Check size during read
                if file_size > settings.max_file_size:
                    max_mb = settings.max_file_size / 1024 / 1024
                    raise HTTPException(
                        status_code=413,
                        detail=f"File too large. Maximum size: {max_mb}MB",
                    )
                temp_file.write(chunk)

        relative_path = f"uploads/{unique_filename}"
        await write_file_from_path(
            relative_path,
            temp_path,
            content_type=file.content_type,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")
    finally:
        if temp_path and Path(temp_path).exists():
            Path(temp_path).unlink(missing_ok=True)

    # Return relative path (not absolute) and size
    return relative_path, file_size
