import time

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.document_repository import search_document_chunks_by_embedding
from app.services.embedding_service import generate_embedding
from app.utils.logging_config import get_logger

logger = get_logger(__name__)


async def search_chunks_from_embedding(
    *,
    document_id: int,
    query_embedding: list[float],
    top_k: int,
    db: AsyncSession,
) -> list[dict]:
    rows = await search_document_chunks_by_embedding(
        db=db,
        document_id=document_id,
        query_embedding=query_embedding,
        top_k=top_k,
    )

    search_results = []
    for chunk_id, content, chunk_index, page_start, page_end, distance in rows:
        similarity = 1 - distance
        search_results.append(
            {
                "chunk_id": chunk_id,
                "content": content,
                "similarity": round(similarity, 4),
                "chunk_index": chunk_index,
                "page_start": page_start,
                "page_end": page_end,
            }
        )

    return search_results


async def search_chunks(query: str, document_id: int, top_k: int, db: AsyncSession) -> list[dict]:
    """
    Search for chunks semantically similar to the query.
    """
    search_results, _, _ = await search_chunks_with_timings(
        query=query,
        document_id=document_id,
        top_k=top_k,
        db=db,
    )
    return search_results


async def search_chunks_with_timings(
    *,
    query: str,
    document_id: int,
    top_k: int,
    db: AsyncSession,
) -> tuple[list[dict], int, int]:
    """
    Search for chunks semantically similar to the query and return timing metadata.
    """
    logger.info(
        f"Searching chunks for document_id={document_id}, top_k={top_k}, query_chars={len(query)}"
    )

    embed_start = time.perf_counter()
    query_embedding = await generate_embedding(query)
    embed_ms = int((time.perf_counter() - embed_start) * 1000)
    logger.debug(f"Generated query embedding with {len(query_embedding)} dimensions")

    retrieval_start = time.perf_counter()
    search_results = await search_chunks_from_embedding(
        document_id=document_id,
        query_embedding=query_embedding,
        top_k=top_k,
        db=db,
    )
    retrieval_ms = int((time.perf_counter() - retrieval_start) * 1000)

    logger.info(f"Found {len(search_results)} results")
    return search_results, embed_ms, retrieval_ms
