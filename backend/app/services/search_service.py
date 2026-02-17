from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import Chunk
from app.services.embedding_service import generate_embedding
from app.utils.logging_config import get_logger

logger = get_logger(__name__)


async def search_chunks(query: str, document_id: int, top_k: int, db: AsyncSession) -> list[dict]:
    """
    Search for chunks semantically similar to the query.
    """
    logger.info(f"Searching for: '{query}' in document_id={document_id}, top_k={top_k}")

    query_embedding = await generate_embedding(query)
    logger.debug(f"Generated query embedding with {len(query_embedding)} dimensions")

    # Create distance expression
    distance_expr = Chunk.embedding.cosine_distance(query_embedding).label("distance")

    stmt = (
        select(Chunk.id, Chunk.content, Chunk.chunk_index, distance_expr)
        .where(Chunk.document_id == document_id)
        .where(Chunk.embedding.isnot(None))
        .order_by(distance_expr)
        .limit(top_k)
    )

    results = (await db.execute(stmt)).all()

    logger.debug(f"Query returned {len(results)} results")

    search_results = []
    for chunk_id, content, chunk_index, distance in results:
        similarity = 1 - distance
        search_results.append(
            {
                "chunk_id": chunk_id,
                "content": content,
                "similarity": round(similarity, 4),
                "chunk_index": chunk_index,
            }
        )

    logger.info(f"Found {len(search_results)} results")
    return search_results
