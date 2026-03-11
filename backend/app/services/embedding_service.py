from contextvars import ContextVar
from dataclasses import dataclass
from time import perf_counter

from openai import AsyncOpenAI, OpenAIError

from app.config import settings
from app.constants import EMBEDDING_DIMENSIONS, EMBEDDING_MODEL
from app.utils.logging_config import get_logger

logger = get_logger(__name__)
_client: AsyncOpenAI | None = None
_last_embedding_usage_tokens: ContextVar[int | None] = ContextVar(
    "embedding_usage_tokens",
    default=None,
)


@dataclass(frozen=True)
class EmbeddingTokenUsage:
    prompt_tokens: int | None


def consume_last_embedding_usage_tokens() -> int | None:
    tokens = _last_embedding_usage_tokens.get()
    _last_embedding_usage_tokens.set(None)
    return tokens


def _extract_embedding_token_usage(response: object) -> EmbeddingTokenUsage:
    usage = getattr(response, "usage", None)
    prompt_tokens = getattr(usage, "prompt_tokens", None)
    if isinstance(prompt_tokens, int):
        return EmbeddingTokenUsage(prompt_tokens=prompt_tokens)
    return EmbeddingTokenUsage(prompt_tokens=None)


def _log_external_call_completed(
    *,
    model: str,
    duration_ms: int,
    usage: EmbeddingTokenUsage,
) -> None:
    extra: dict[str, object] = {
        "event": "external.call_completed",
        "provider": "openai",
        "model": model,
        "duration_ms": duration_ms,
    }
    if usage.prompt_tokens is not None:
        extra["embedding_tokens"] = usage.prompt_tokens
    logger.info("external.call_completed", extra=extra)


def _log_external_call_failed(
    *,
    model: str,
    duration_ms: int,
    error: Exception,
) -> None:
    logger.warning(
        "external.call_failed",
        extra={
            "event": "external.call_failed",
            "provider": "openai",
            "model": model,
            "duration_ms": duration_ms,
            "error_class": type(error).__name__,
        },
    )


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

    _last_embedding_usage_tokens.set(None)
    call_start = perf_counter()
    try:
        logger.debug(f"Generating embedding for text (length={len(text)})")

        client = _get_client()

        response = await client.embeddings.create(
            model=EMBEDDING_MODEL, input=text, encoding_format="float"
        )
        usage = _extract_embedding_token_usage(response)
        _last_embedding_usage_tokens.set(usage.prompt_tokens)

        embedding = response.data[0].embedding

        if len(embedding) != EMBEDDING_DIMENSIONS:
            raise ValueError(
                f"Expected {EMBEDDING_DIMENSIONS} dimensions, got {len(embedding)}"
            )

        _log_external_call_completed(
            model=EMBEDDING_MODEL,
            duration_ms=int((perf_counter() - call_start) * 1000),
            usage=usage,
        )
        logger.debug("Embedding generated successfully")
        return embedding

    except OpenAIError as e:
        _log_external_call_failed(
            model=EMBEDDING_MODEL,
            duration_ms=int((perf_counter() - call_start) * 1000),
            error=e,
        )
        logger.error(f"OpenAI API error: {e}")
        raise

    except Exception as e:
        _log_external_call_failed(
            model=EMBEDDING_MODEL,
            duration_ms=int((perf_counter() - call_start) * 1000),
            error=e,
        )
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

    _last_embedding_usage_tokens.set(None)
    call_start = perf_counter()
    try:
        logger.info(f"Generating embeddings for {len(texts)} texts")

        client = _get_client()

        response = await client.embeddings.create(
            model=EMBEDDING_MODEL, input=texts, encoding_format="float"
        )
        usage = _extract_embedding_token_usage(response)
        _last_embedding_usage_tokens.set(usage.prompt_tokens)

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

        _log_external_call_completed(
            model=EMBEDDING_MODEL,
            duration_ms=int((perf_counter() - call_start) * 1000),
            usage=usage,
        )
        logger.info(f"Generated {len(ordered_embeddings)} embeddings successfully")
        return ordered_embeddings

    except OpenAIError as e:
        _log_external_call_failed(
            model=EMBEDDING_MODEL,
            duration_ms=int((perf_counter() - call_start) * 1000),
            error=e,
        )
        logger.error(f"OpenAI API error: {e}")
        raise

    except Exception as e:
        _log_external_call_failed(
            model=EMBEDDING_MODEL,
            duration_ms=int((perf_counter() - call_start) * 1000),
            error=e,
        )
        logger.error(f"Unexpected error generating embeddings: {e}", exc_info=True)
        raise
