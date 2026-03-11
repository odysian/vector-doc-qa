from pydantic import BaseModel, Field

from app.schemas.search import SearchResult


class QueryRequest(BaseModel):
    """Request to ask a question about a document"""

    query: str = Field(..., min_length=1)


class PipelineMeta(BaseModel):
    """Timing and retrieval metadata for query pipeline observability."""

    embed_ms: int
    retrieval_ms: int
    llm_ms: int
    total_ms: int
    top_similarity: float
    avg_similarity: float
    chunks_retrieved: int
    chunks_above_threshold: int
    similarity_spread: float
    chat_history_turns_included: int
    embedding_tokens: int | None = None
    llm_input_tokens: int | None = None
    llm_output_tokens: int | None = None


class QueryResponse(BaseModel):
    """Response containing AI-generated answer with sources."""

    query: str
    answer: str
    sources: list[SearchResult]
    pipeline_meta: PipelineMeta | None = None
