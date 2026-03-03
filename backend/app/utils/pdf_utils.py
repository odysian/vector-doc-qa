# backend/app/utils/pdf_utils.py
from dataclasses import dataclass
import io

import pdfplumber

from app.config import settings
from app.constants import PDF_PROCESSING_TIMEOUT_SECONDS
from app.utils.timeout import run_with_timeout_async


@dataclass(slots=True, frozen=True)
class PageBoundary:
    """Marks the exclusive end character offset for one source PDF page."""

    page_number: int
    end_char: int


@dataclass(slots=True, frozen=True)
class ExtractedPdfText:
    """Extracted PDF text plus page boundary offsets in the joined text."""

    text: str
    page_boundaries: list[PageBoundary]


@dataclass(slots=True, frozen=True)
class ChunkWithPage:
    """Chunk content with optional page span metadata."""

    content: str
    page_start: int | None = None
    page_end: int | None = None


def _extract_text_and_page_boundaries(pdf: pdfplumber.PDF) -> ExtractedPdfText:
    text_parts: list[str] = []
    page_boundaries: list[PageBoundary] = []
    current_offset = 0

    for page_number, page in enumerate(pdf.pages, start=1):
        page_text = page.extract_text()
        if not page_text:
            continue

        if text_parts:
            separator = "\n\n"
            text_parts.append(separator)
            current_offset += len(separator)

        text_parts.append(page_text)
        current_offset += len(page_text)
        page_boundaries.append(PageBoundary(page_number=page_number, end_char=current_offset))

    return ExtractedPdfText(text="".join(text_parts), page_boundaries=page_boundaries)


def _do_pdf_extraction_with_page_boundaries(pdf_path: str) -> ExtractedPdfText:
    """Extract text + page boundaries from a PDF path in a subprocess."""
    with pdfplumber.open(pdf_path) as pdf:
        return _extract_text_and_page_boundaries(pdf)


def _do_pdf_extraction(pdf_path: str) -> str:
    """Extract text from PDF. Runs in a subprocess via ProcessPoolExecutor."""
    extracted = _do_pdf_extraction_with_page_boundaries(pdf_path)
    return extracted.text


async def extract_text_with_page_boundaries_from_pdf(pdf_path: str) -> ExtractedPdfText:
    """
    Extract text and page boundaries from a PDF file with timeout protection.
    """
    try:
        return await run_with_timeout_async(
            _do_pdf_extraction_with_page_boundaries,
            (pdf_path,),
            PDF_PROCESSING_TIMEOUT_SECONDS,
        )
    except TimeoutError:
        raise TimeoutError(
            f"PDF processing timed out after {PDF_PROCESSING_TIMEOUT_SECONDS} seconds. "
            "This PDF may contain complex graphics or be image-based."
        )


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


def _do_pdf_extraction_from_bytes_with_page_boundaries(pdf_bytes: bytes) -> ExtractedPdfText:
    """Extract text + page boundaries from PDF bytes in a subprocess."""
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        return _extract_text_and_page_boundaries(pdf)


def _do_pdf_extraction_from_bytes(pdf_bytes: bytes) -> str:
    """Extract text from PDF bytes. Runs in subprocess via ProcessPoolExecutor."""
    extracted = _do_pdf_extraction_from_bytes_with_page_boundaries(pdf_bytes)
    return extracted.text


async def extract_text_from_pdf_bytes(pdf_bytes: bytes) -> str:
    """
    Extract all text from PDF bytes with timeout protection.

    Uses the same timeout/executor behavior as path-based extraction.
    """
    try:
        text = await run_with_timeout_async(
            _do_pdf_extraction_from_bytes,
            (pdf_bytes,),
            PDF_PROCESSING_TIMEOUT_SECONDS,
        )
        return text
    except TimeoutError:
        raise TimeoutError(
            f"PDF processing timed out after {PDF_PROCESSING_TIMEOUT_SECONDS} seconds. "
            "This PDF may contain complex graphics or be image-based."
        )


async def extract_text_with_page_boundaries_from_pdf_bytes(
    pdf_bytes: bytes,
) -> ExtractedPdfText:
    """
    Extract text and page boundaries from PDF bytes with timeout protection.
    """
    try:
        return await run_with_timeout_async(
            _do_pdf_extraction_from_bytes_with_page_boundaries,
            (pdf_bytes,),
            PDF_PROCESSING_TIMEOUT_SECONDS,
        )
    except TimeoutError:
        raise TimeoutError(
            f"PDF processing timed out after {PDF_PROCESSING_TIMEOUT_SECONDS} seconds. "
            "This PDF may contain complex graphics or be image-based."
        )


def _page_for_char_offset(
    *,
    char_offset: int,
    page_boundaries: list[PageBoundary],
) -> int | None:
    for boundary in page_boundaries:
        if char_offset < boundary.end_char:
            return boundary.page_number
    return page_boundaries[-1].page_number if page_boundaries else None


def _map_chunk_range_to_pages(
    *,
    chunk_start: int,
    chunk_end: int,
    page_boundaries: list[PageBoundary],
) -> tuple[int | None, int | None]:
    if chunk_start >= chunk_end or not page_boundaries:
        return None, None

    page_start = _page_for_char_offset(char_offset=chunk_start, page_boundaries=page_boundaries)
    page_end = _page_for_char_offset(
        char_offset=chunk_end - 1,
        page_boundaries=page_boundaries,
    )
    return page_start, page_end


def chunk_text(
    text: str,
    chunk_size: int | None = None,
    overlap: int | None = None,
    page_boundaries: list[PageBoundary] | None = None,
) -> list[ChunkWithPage]:
    """
    Split text into overlapping chunks.

    Args:
        text: Full text to chunk
        chunk_size: Characters per chunk (defaults to settings.chunk_size)
        overlap: Characters to overlap (defaults to settings.chunk_overlap)

    Returns:
        List of chunk payloads (content + optional page_start/page_end)
    """
    # Use settings defaults
    if chunk_size is None:
        chunk_size = settings.chunk_size
    if overlap is None:
        overlap = settings.chunk_overlap

    # Edge cases
    if not text or not text.strip():
        return []

    effective_page_boundaries = page_boundaries or []

    if len(text) <= chunk_size:
        page_start, page_end = _map_chunk_range_to_pages(
            chunk_start=0,
            chunk_end=len(text),
            page_boundaries=effective_page_boundaries,
        )
        return [ChunkWithPage(content=text, page_start=page_start, page_end=page_end)]

    # Chunk the text
    chunks = []
    start = 0

    while start < len(text):
        # Target end position
        end = min(start + chunk_size, len(text))

        # If not at the end of the text, find the last space before end
        if end < len(text):
            # Look backwards from end to find space
            while end > start and not text[end].isspace():
                end -= 1

            # If no space found, cut at chunk size
            if end == start:
                end = min(start + chunk_size, len(text))

        # Trim chunk boundaries for cleaner text but keep original character
        # offsets so page mapping stays accurate.
        chunk_start = start
        while chunk_start < end and text[chunk_start].isspace():
            chunk_start += 1

        chunk_end = end
        while chunk_end > chunk_start and text[chunk_end - 1].isspace():
            chunk_end -= 1

        # Validate not an empty chunk
        if chunk_end > chunk_start:
            page_start, page_end = _map_chunk_range_to_pages(
                chunk_start=chunk_start,
                chunk_end=chunk_end,
                page_boundaries=effective_page_boundaries,
            )
            chunks.append(
                ChunkWithPage(
                    content=text[chunk_start:chunk_end],
                    page_start=page_start,
                    page_end=page_end,
                )
            )

        if end >= len(text):
            break

        # Move forward with overlap
        next_start = end - overlap
        if next_start <= start:
            next_start = start + 1
        start = next_start

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
