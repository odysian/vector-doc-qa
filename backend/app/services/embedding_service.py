from openai import AsyncOpenAI, OpenAIError

from app.config import settings
from app.constants import EMBEDDING_DIMENSIONS, EMBEDDING_MODEL
from app.utils.logging_config import get_logger

logger = get_logger(__name__)
_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=settings.openai_api_key)
    return _client


async def generate_embedding(text: str) -> list[float]:
    """Generate a vector embedding for a single text string"""

    # Keep single-item and batch behavior aligned: blank input is always invalid.
    if not text or not text.strip():
        raise ValueError("Cannot generate embedding for empty text")

    try:
        logger.debug(f"Generating embedding for text (length={len(text)})")

        client = _get_client()

        response = await client.embeddings.create(
            model=EMBEDDING_MODEL, input=text, encoding_format="float"
        )

        embedding = response.data[0].embedding

        if len(embedding) != EMBEDDING_DIMENSIONS:
            raise ValueError(
                f"Expected {EMBEDDING_DIMENSIONS} dimensions, got {len(embedding)}"
            )

        logger.debug("Embedding generated successfully")
        return embedding

    except OpenAIError as e:
        logger.error(f"OpenAI API error: {e}")
        raise

    except Exception as e:
        logger.error(f"Unexpected error generating embedding: {e}", exc_info=True)
        raise


async def generate_embeddings_batch(texts: list[str]) -> list[list[float]]:
    """
    Generate embeddings for multiple texts in a single API call.

    Contract:
    - `texts` must be a non-empty list of non-whitespace strings.
    - Returned embeddings always match `texts` 1:1 by index and order.
    """

    if not texts:
        raise ValueError("Cannot generate embeddings for empty list")

    # Fail fast instead of filtering so callers never lose position alignment silently.
    for index, text in enumerate(texts):
        if not isinstance(text, str) or not text.strip():
            raise ValueError(
                f"Invalid batch text at index {index}: must be a non-empty string"
            )

    try:
        logger.info(f"Generating embeddings for {len(texts)} texts")

        client = _get_client()

        response = await client.embeddings.create(
            model=EMBEDDING_MODEL, input=texts, encoding_format="float"
        )

        # Build a map by provider-reported index so we can enforce deterministic
        # input-order output even if the API response ordering changes.
        embeddings_by_index: dict[int, list[float]] = {}
        for item in response.data:
            if item.index in embeddings_by_index:
                raise ValueError(f"Duplicate embedding index in response: {item.index}")
            if len(item.embedding) != EMBEDDING_DIMENSIONS:
                raise ValueError(
                    f"Expected {EMBEDDING_DIMENSIONS} dimensions, got {len(item.embedding)}"
                )
            embeddings_by_index[item.index] = item.embedding

        if len(embeddings_by_index) != len(texts):
            raise ValueError(
                f"Expected {len(texts)} embeddings, got {len(embeddings_by_index)}"
            )

        # Reconstruct in original input order and fail if any index is missing.
        ordered_embeddings: list[list[float]] = []
        for index in range(len(texts)):
            if index not in embeddings_by_index:
                raise ValueError(f"Missing embedding at index {index}")
            ordered_embeddings.append(embeddings_by_index[index])

        logger.info(f"Generated {len(ordered_embeddings)} embeddings successfully")
        return ordered_embeddings

    except OpenAIError as e:
        logger.error(f"OpenAI API error: {e}")
        raise

    except Exception as e:
        logger.error(f"Unexpected error generating embeddings: {e}", exc_info=True)
        raise
