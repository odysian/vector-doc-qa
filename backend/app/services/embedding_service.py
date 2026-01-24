from typing import List

from openai import OpenAI, OpenAIError

from app.config import settings
from app.constants import EMBEDDING_DIMENSIONS, EMBEDDING_MODEL
from app.utils.logging_config import get_logger

logger = get_logger(__name__)


def generate_embedding(text: str) -> List[float]:
    """Generate a vector embedding for a single text string"""

    if not text or not text.strip():
        raise ValueError("Cannot generate embedding for empty text")

    try:
        logger.debug(f"Generating embedding for text (length={len(text)})")

        client = OpenAI(api_key=settings.openai_api_key)

        response = client.embeddings.create(
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


def generate_embeddings_batch(texts: List[str]) -> List[List[float]]:
    """Generate embeddings for multiple texts in a single API call"""

    if not texts:
        raise ValueError("Cannot generate embeddings for empty list")

    valid_texts = [t for t in texts if t and t.strip()]

    if not valid_texts:
        raise ValueError("No valid texts to embed (all empty)")

    try:
        logger.info(f"Generating embeddings for {len(valid_texts)} texts")

        client = OpenAI(api_key=settings.openai_api_key)

        response = client.embeddings.create(
            model=EMBEDDING_MODEL, input=valid_texts, encoding_format="float"
        )

        embeddings = [item.embedding for item in response.data]

        if len(embeddings) != len(valid_texts):
            raise ValueError(
                f"Expected {len(valid_texts)} embeddings, got {len(embeddings)}"
            )

        logger.info(f"Generated {len(embeddings)} embeddings successfully")
        return embeddings

    except OpenAIError as e:
        logger.error(f"OpenAI API error: {e}")
        raise

    except Exception as e:
        logger.error(f"Unexpected error generating embeddings: {e}", exc_info=True)
        raise
