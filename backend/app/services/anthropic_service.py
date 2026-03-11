from collections.abc import AsyncGenerator
from contextvars import ContextVar
from dataclasses import dataclass
from time import perf_counter

from anthropic import APIStatusError, AsyncAnthropic

from app.config import settings
from app.utils.logging_config import get_logger

logger = get_logger(__name__)
_client: AsyncAnthropic | None = None
ANTHROPIC_MODEL = "claude-3-haiku-20240307"


@dataclass(frozen=True)
class LlmTokenUsage:
    input_tokens: int | None
    output_tokens: int | None


_last_answer_usage: ContextVar[LlmTokenUsage | None] = ContextVar(
    "anthropic_answer_usage",
    default=None,
)
_last_stream_usage: ContextVar[LlmTokenUsage | None] = ContextVar(
    "anthropic_stream_usage",
    default=None,
)


def consume_last_answer_usage() -> LlmTokenUsage | None:
    usage = _last_answer_usage.get()
    _last_answer_usage.set(None)
    return usage


def consume_last_stream_usage() -> LlmTokenUsage | None:
    usage = _last_stream_usage.get()
    _last_stream_usage.set(None)
    return usage


def _extract_llm_token_usage(usage_payload: object) -> LlmTokenUsage | None:
    if usage_payload is None:
        return None

    raw_input_tokens = getattr(usage_payload, "input_tokens", None)
    raw_output_tokens = getattr(usage_payload, "output_tokens", None)
    raw_cache_creation_tokens = getattr(usage_payload, "cache_creation_input_tokens", None)
    raw_cache_read_tokens = getattr(usage_payload, "cache_read_input_tokens", None)

    input_tokens = raw_input_tokens if isinstance(raw_input_tokens, int) else None
    output_tokens = raw_output_tokens if isinstance(raw_output_tokens, int) else None
    cache_creation_tokens = (
        raw_cache_creation_tokens if isinstance(raw_cache_creation_tokens, int) else None
    )
    cache_read_tokens = raw_cache_read_tokens if isinstance(raw_cache_read_tokens, int) else None

    if input_tokens is not None:
        input_tokens += (cache_creation_tokens or 0) + (cache_read_tokens or 0)

    if input_tokens is None and output_tokens is None:
        return None
    return LlmTokenUsage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )


def _log_external_call_completed(*, duration_ms: int, usage: LlmTokenUsage | None) -> None:
    extra: dict[str, object] = {
        "event": "external.call_completed",
        "provider": "anthropic",
        "model": ANTHROPIC_MODEL,
        "duration_ms": duration_ms,
    }
    if usage is not None:
        if usage.input_tokens is not None:
            extra["llm_input_tokens"] = usage.input_tokens
        if usage.output_tokens is not None:
            extra["llm_output_tokens"] = usage.output_tokens
    logger.info("external.call_completed", extra=extra)


def _log_external_call_failed(
    *,
    duration_ms: int,
    error: Exception,
    status_code: int | None = None,
) -> None:
    extra: dict[str, object] = {
        "event": "external.call_failed",
        "provider": "anthropic",
        "model": ANTHROPIC_MODEL,
        "duration_ms": duration_ms,
        "error_class": type(error).__name__,
    }
    if status_code is not None:
        extra["status_code"] = status_code
    logger.warning("external.call_failed", extra=extra)


def _get_client() -> AsyncAnthropic:
    global _client
    if _client is None:
        _client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    return _client


def _build_prompt(
    query: str,
    chunks: list[dict],
    conversation_history: list[dict[str, str]] | None = None,
) -> str:
    """
    Build the prompt for Claude with chunks embedded

    Args:
        query: User's question
        chunks: Search results with content
    Returns:
        Formatted prompt string
    """

    has_document_filenames = any(
        isinstance(chunk, dict) and chunk.get("document_filename")
        for chunk in chunks
    )

    excerpts = []
    for i, chunk in enumerate(chunks, 1):
        document_filename = chunk.get("document_filename")
        if has_document_filenames and document_filename:
            excerpt = f'Excerpt {i} (from "{document_filename}"):\n{chunk["content"]}'
        else:
            excerpt = f"Excerpt {i}:\n{chunk['content']}"
        excerpts.append(excerpt)

    excerpts_text = "\n\n".join(excerpts)

    history_lines: list[str] = []
    for message in conversation_history or []:
        role = message.get("role", "").strip().lower()
        content = message.get("content", "").strip()
        if not content:
            continue
        if role == "user":
            history_lines.append(f"User: {content}")
            continue
        if role == "assistant":
            history_lines.append(f"Assistant: {content}")

    history_section = ""
    if history_lines:
        history_section = (
            "Recent conversation history (oldest to newest):\n"
            + "\n".join(history_lines)
            + "\n\n"
        )

    excerpts_intro = "Here are excerpts from a document:"
    citation_instruction = ""
    if has_document_filenames:
        excerpts_intro = "Here are excerpts from multiple documents:"
        citation_instruction = (
            "\nWhen citing information, mention which document it came from."
        )

    prompt = f"""{excerpts_intro}

{excerpts_text}

{history_section}Current question: {query}

You are a helpful assistant. Answer the user's question using only the provided excerpts.

If the specific answer is not explicitly stated, synthesize relevant details from the text that address the core of the user's inquiry.

If the excerpts contain absolutely no relevant information, state that you cannot answer based on the provided text.{citation_instruction}"""

    return prompt


async def generate_answer(
    query: str,
    chunks: list[dict],
    conversation_history: list[dict[str, str]] | None = None,
) -> str:
    """
    Calls Claude API to generate an answer to user query.
    Args:
        query: "What was Q4 revenue?"
        chunks: [
            {"chunk_id": 42, "content": "...", "similarity": 0.85},
            {"chunk_id": 45, "content": "...", "similarity": 0.82}
        ]

    Returns:
        "Based on the document, Q4 revenue was $5M..."
    """

    logger.info(f"Generating answer with query_chars={len(query)}, chunk_count={len(chunks)}")

    prompt = _build_prompt(query, chunks, conversation_history)
    logger.debug(f"Built prompt with {len(chunks)} chunks")

    _last_answer_usage.set(None)
    call_start = perf_counter()
    try:
        client = _get_client()
        response = await client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        usage = _extract_llm_token_usage(getattr(response, "usage", None))
        _last_answer_usage.set(usage)
        answer = response.content[0].text  # type: ignore

        _log_external_call_completed(
            duration_ms=int((perf_counter() - call_start) * 1000),
            usage=usage,
        )
        logger.info(f"Answer length: {len(answer)} characters")
        return answer

    except APIStatusError as e:
        _log_external_call_failed(
            duration_ms=int((perf_counter() - call_start) * 1000),
            error=e,
            status_code=e.status_code,
        )
        # Check for 529 Overloaded code
        if e.status_code == 529:
            logger.warning("Anthropic API is overloaded (HTTP 529).")
            return "I'm sorry, the AI service is currently overloaded. Please try again in a few minutes."

        # Handle other API errors
        logger.error(f"Anthropic API returned an error: {e.status_code} - {e.message}")
        return "I encountered an error communicating with the AI service. Please try again later."

    except Exception as e:
        _log_external_call_failed(
            duration_ms=int((perf_counter() - call_start) * 1000),
            error=e,
        )
        logger.error(f"Unexpected error generating answer: {e}", exc_info=True)
        raise


async def generate_answer_stream(
    query: str,
    chunks: list[dict],
    conversation_history: list[dict[str, str]] | None = None,
) -> AsyncGenerator[str, None]:
    """
    Calls Claude streaming API and yields answer tokens as they arrive.
    """
    logger.info(
        f"Generating streaming answer with query_chars={len(query)}, chunk_count={len(chunks)}"
    )

    prompt = _build_prompt(query, chunks, conversation_history)
    logger.debug(f"Built prompt with {len(chunks)} chunks")

    _last_stream_usage.set(None)
    call_start = perf_counter()
    try:
        client = _get_client()
        async with client.messages.stream(
            model=ANTHROPIC_MODEL,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            async for token in stream.text_stream:
                if token:
                    yield token

            get_final_message = getattr(stream, "get_final_message", None)
            usage = None
            if callable(get_final_message):
                final_message = await get_final_message()
                usage = _extract_llm_token_usage(getattr(final_message, "usage", None))

            _last_stream_usage.set(usage)
            _log_external_call_completed(
                duration_ms=int((perf_counter() - call_start) * 1000),
                usage=usage,
            )
    except APIStatusError as e:
        _log_external_call_failed(
            duration_ms=int((perf_counter() - call_start) * 1000),
            error=e,
            status_code=e.status_code,
        )
        if e.status_code == 529:
            logger.warning("Anthropic streaming API is overloaded (HTTP 529).")
            yield "I'm sorry, the AI service is currently overloaded. Please try again in a few minutes."
            return

        logger.error(
            f"Anthropic streaming API returned an error: {e.status_code} - {e.message}",
            exc_info=True,
        )
        yield "I encountered an error communicating with the AI service. Please try again later."
        return
    except Exception as e:
        _log_external_call_failed(
            duration_ms=int((perf_counter() - call_start) * 1000),
            error=e,
        )
        logger.error(f"Unexpected error generating streaming answer: {e}", exc_info=True)
        raise
