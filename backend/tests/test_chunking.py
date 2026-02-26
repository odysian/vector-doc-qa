# tests/test_chunking.py
"""Tests for text chunking algorithm in pdf_utils.chunk_text."""

from app.utils.pdf_utils import chunk_text


class TestChunkTextBasic:
    """Basic chunking behavior."""

    def test_empty_string_returns_empty_list(self):
        assert chunk_text("", chunk_size=100, overlap=10) == []

    def test_whitespace_only_returns_empty_list(self):
        assert chunk_text("   \n\t  ", chunk_size=100, overlap=10) == []

    def test_text_shorter_than_chunk_size_returns_single_chunk(self):
        text = "Hello world"
        result = chunk_text(text, chunk_size=100, overlap=10)
        assert result == [text]

    def test_text_equal_to_chunk_size_returns_single_chunk(self):
        text = "a" * 100
        result = chunk_text(text, chunk_size=100, overlap=10)
        assert result == [text]

    def test_all_text_is_covered(self):
        """Every character in the original text appears in at least one chunk."""
        text = " ".join(f"word{i}" for i in range(200))
        chunks = chunk_text(text, chunk_size=100, overlap=20)
        merged = set()
        for chunk in chunks:
            idx = text.find(chunk)
            assert idx != -1, f"Chunk not found in original text: {chunk!r}"
            for i in range(idx, idx + len(chunk)):
                merged.add(i)
        # Every non-whitespace position should be covered
        for i, ch in enumerate(text):
            if not ch.isspace():
                assert i in merged, (
                    f"Character at position {i} ({ch!r}) not in any chunk"
                )


class TestChunkWordBoundaries:
    """Chunks must start and end on word boundaries."""

    def test_chunks_do_not_start_mid_word(self):
        """The original bug: start of chunks 2+ could split a word."""
        text = " ".join(f"word{i}" for i in range(200))
        chunks = chunk_text(text, chunk_size=100, overlap=20)
        for i, chunk in enumerate(chunks):
            assert not chunk[0].isspace(), (
                f"Chunk {i} starts with whitespace"
            )
            # First char should be the start of a word — verify the char
            # before this chunk in the original text is a space or this is
            # the first chunk
            idx = text.find(chunk)
            if idx > 0:
                assert text[idx - 1].isspace(), (
                    f"Chunk {i} starts mid-word: "
                    f"...{text[max(0,idx-5):idx+10]!r}..."
                )

    def test_chunks_do_not_end_mid_word(self):
        """End of each chunk (except possibly the last) should be a word boundary."""
        text = " ".join(f"word{i}" for i in range(200))
        chunks = chunk_text(text, chunk_size=100, overlap=20)
        for i, chunk in enumerate(chunks[:-1]):
            idx = text.find(chunk)
            end_pos = idx + len(chunk)
            if end_pos < len(text):
                assert text[end_pos].isspace(), (
                    f"Chunk {i} ends mid-word: "
                    f"...{text[end_pos-5:end_pos+5]!r}..."
                )


class TestChunkOverlap:
    """Overlap between consecutive chunks."""

    def test_consecutive_chunks_share_content(self):
        """Adjacent chunks should have overlapping text."""
        text = " ".join(f"word{i}" for i in range(200))
        chunks = chunk_text(text, chunk_size=100, overlap=20)
        assert len(chunks) > 2, "Need multiple chunks to test overlap"
        for i in range(len(chunks) - 1):
            # The end of chunk[i] should overlap with the start of chunk[i+1]
            # Find where chunk[i+1] starts in original text
            idx_a = text.find(chunks[i])
            idx_b = text.find(chunks[i + 1])
            end_a = idx_a + len(chunks[i])
            assert idx_b < end_a, (
                f"Chunks {i} and {i+1} have no overlap: "
                f"chunk {i} ends at {end_a}, chunk {i+1} starts at {idx_b}"
            )

    def test_zero_overlap(self):
        """With overlap=0, chunks should not share content."""
        text = " ".join(f"word{i}" for i in range(200))
        chunks = chunk_text(text, chunk_size=100, overlap=0)
        assert len(chunks) > 1
        for i in range(len(chunks) - 1):
            idx_a = text.find(chunks[i])
            idx_b = text.find(chunks[i + 1])
            end_a = idx_a + len(chunks[i])
            assert idx_b >= end_a, (
                f"Chunks {i} and {i+1} overlap with overlap=0"
            )


class TestChunkEdgeCases:
    """Edge cases and stress tests."""

    def test_no_spaces_in_text(self):
        """A single long token with no word boundaries."""
        text = "a" * 250
        chunks = chunk_text(text, chunk_size=100, overlap=20)
        # Should still produce chunks covering all text
        combined = "".join(chunks)
        assert "a" * 250 in combined or len(combined) >= 250

    def test_tail_is_not_dropped(self):
        """Small tail shorter than overlap must not be silently lost."""
        # 1000 chars of words + a small unique tail
        words = " ".join(f"word{i}" for i in range(150))
        tail = " UNIQUETAIL"
        text = words + tail
        chunks = chunk_text(text, chunk_size=100, overlap=20)
        last_chunk = chunks[-1]
        assert "UNIQUETAIL" in last_chunk, (
            f"Tail was dropped. Last chunk: {last_chunk!r}"
        )

    def test_very_large_overlap_near_chunk_size(self):
        """Overlap almost as large as chunk_size should still terminate."""
        text = " ".join(f"w{i}" for i in range(500))
        chunks = chunk_text(text, chunk_size=100, overlap=90)
        assert len(chunks) > 0
        # Verify all text is covered
        assert chunks[-1] in text

    def test_single_space_separated_words(self):
        """Standard prose-like text."""
        text = "The quick brown fox jumps over the lazy dog and keeps running across the field"
        chunks = chunk_text(text, chunk_size=30, overlap=10)
        assert len(chunks) > 1
        for chunk in chunks:
            # No chunk should start or end with a space
            assert chunk == chunk.strip()

    def test_multiline_text_from_pdf(self):
        """Text with newlines (as produced by PDF page joins)."""
        text = "First paragraph with some words.\n\nSecond paragraph continues here.\n\nThird paragraph at the end."
        chunks = chunk_text(text, chunk_size=40, overlap=10)
        assert len(chunks) > 1
        # All text should be recoverable
        for word in ["First", "Second", "Third", "end"]:
            assert any(word in c for c in chunks), f"{word!r} missing from chunks"
