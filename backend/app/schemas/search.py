from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    """Request to search for similar chunks."""

    query: str = Field(..., min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)


class SearchResult(BaseModel):
    """A single search result."""

    chunk_id: int
    content: str
    similarity: float = Field(...)
    chunk_index: int
    page_start: int | None = None
    page_end: int | None = None


class SearchResponse(BaseModel):
    """Response containing search results."""

    query: str
    document_id: int
    results: list[SearchResult]
    total_results: int
