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
    logger.info(
        f"Searching chunks for document_id={document_id}, top_k={top_k}, query_chars={len(query)}"
    )

    query_embedding = await generate_embedding(query)
    logger.debug(f"Generated query embedding with {len(query_embedding)} dimensions")

    search_results = await search_chunks_from_embedding(
        document_id=document_id,
        query_embedding=query_embedding,
        top_k=top_k,
        db=db,
    )

    logger.info(f"Found {len(search_results)} results")
    return search_results
