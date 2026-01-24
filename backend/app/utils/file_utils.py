import os
import secrets
from datetime import datetime
from pathlib import Path

from fastapi import HTTPException, UploadFile

from app.config import settings
from app.constants import UPLOAD_CHUNK_SIZE_BYTES


# File Validation
def validate_file_upload(file: UploadFile) -> None:
    """
    Validate uploaded file for security and correctness.

    Checks:
    1. File has a filename
    2. File extension is allowed (.pdf)
    3. File size is within limit

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
    Save uploaded file to disk.

    Returns:
        tuple: (file_path, file_size)

    Security:
    - Validates file during read
    - Uses unique filename
    - Stores in dedicated uploads directory
    """

    unique_filename = generate_unique_filename(file.filename)  # type: ignore

    # Get upload dir path
    upload_dir = settings.get_upload_path()
    file_path = upload_dir / unique_filename

    # Read and write file in chunks (memory efficient)
    file_size = 0
    chunk_size = UPLOAD_CHUNK_SIZE_BYTES  # 1MB chunks

    try:
        with open(file_path, "wb") as f:
            while chunk := await file.read(chunk_size):
                file_size += len(chunk)

                # Check size during read
                if file_size > settings.max_file_size:
                    f.close()
                    os.remove(file_path)

                    max_mb = settings.max_file_size / 1024 / 1024
                    raise HTTPException(
                        status_code=413,
                        detail=f"File too large. Maximum size: {max_mb}MB",
                    )
                f.write(chunk)

    except HTTPException:
        raise
    except Exception as e:
        # Catch any other errors (disk full, permissions, etc)
        # Clean up partial file if exists
        if file_path.exists():
            os.remove(file_path)

        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")

    # Return relative path (not absolute) and size
    relative_path = f"uploads/{unique_filename}"
    return relative_path, file_size
