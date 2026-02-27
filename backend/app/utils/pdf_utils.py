# backend/app/utils/pdf_utils.py
from typing import List

import pdfplumber

from app.config import settings
from app.constants import PDF_PROCESSING_TIMEOUT_SECONDS
from app.utils.timeout import run_with_timeout_async


def _do_pdf_extraction(pdf_path: str) -> str:
    """Extract text from PDF. Runs in a subprocess via ProcessPoolExecutor."""
    text_parts = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)

    return "\n\n".join(text_parts)


async def extract_text_from_pdf(pdf_path: str) -> str:
    """
    Extract all text from a PDF file with timeout protection.

    Offloads CPU-bound extraction to a process pool so the caller's
    event loop is not blocked.

    Args:
        pdf_path: Path to PDF file

    Returns:
        Extracted text as a single string
    """

    try:
        text = await run_with_timeout_async(
            _do_pdf_extraction, (pdf_path,), PDF_PROCESSING_TIMEOUT_SECONDS
        )
        return text
    except TimeoutError:
        raise TimeoutError(
            f"PDF processing timed out after {PDF_PROCESSING_TIMEOUT_SECONDS} seconds. "
            "This PDF may contain complex graphics or be image-based."
        )


def chunk_text(
    text: str, chunk_size: int | None = None, overlap: int | None = None
) -> List[str]:
    """
    Split text into overlapping chunks.

    Args:
        text: Full text to chunk
        chunk_size: Characters per chunk (defaults to settings.chunk_size)
        overlap: Characters to overlap (defaults to settings.chunk_overlap)

    Returns:
        List of text chunks
    """
    # Use settings defaults
    if chunk_size is None:
        chunk_size = settings.chunk_size
    if overlap is None:
        overlap = settings.chunk_overlap

    # Edge cases
    if not text or not text.strip():
        return []

    if len(text) <= chunk_size:
        return [text]

    # Chunk the text
    chunks = []
    start = 0

    while start < len(text):
        # Target end position
        end = start + chunk_size

        # If not at the end of the text, find the last space before end
        if end < len(text):
            # Look backwards from end to find space
            while end > start and not text[end].isspace():
                end -= 1

            # If no space found, cut at chunk size
            if end == start:
                end = start + chunk_size

        chunk = text[start:end].strip()
        # Validate not an empty chunk
        if chunk:
            chunks.append(chunk)

        # Move forward with overlap
        start = end - overlap

        # Snap start forward to next word boundary so chunks
        # don't begin mid-word
        if start > 0 and start < len(text):
            # Skip past the partial word
            while start < end and not text[start].isspace():
                start += 1
            # Skip past whitespace to land on next word
            while start < end and text[start].isspace():
                start += 1

    return chunks
