from pydantic import BaseModel, Field

from app.schemas.search import SearchResult


class QueryRequest(BaseModel):
    """Request to ask a question about a document"""

    query: str = Field(..., min_length=1)


class QueryResponse(BaseModel):
    """Response containing AI-generated answer with sources."""

    query: str
    answer: str
    sources: list[SearchResult]
