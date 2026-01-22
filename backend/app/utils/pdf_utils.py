# backend/app/utils/pdf_utils.py
from pathlib import Path
from typing import List

import pdfplumber

from app.config import settings


def extract_text_from_pdf(pdf_path: str) -> str:
    """
    Extract all text from a PDF file.

    Args:
        pdf_path: Path to PDF file

    Returns:
        Extracted text as a single string
    """
    text_parts = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)

    full_text = "\n\n".join(text_parts)
    return full_text


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
        end = start + chunk_size
        chunk = text[start:end]
        chunks.append(chunk)

        # Move forward with overlap
        start = end - overlap

        # Safety: prevent infinite loop
        if overlap >= chunk_size:
            start = end

    return chunks
