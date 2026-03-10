from collections.abc import AsyncGenerator

from anthropic import APIStatusError, AsyncAnthropic

from app.config import settings
from app.utils.logging_config import get_logger

logger = get_logger(__name__)
_client: AsyncAnthropic | None = None


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

    logger.info(
        f"Generating answer with query_chars={len(query)}, chunk_count={len(chunks)}"
    )

    prompt = _build_prompt(query, chunks, conversation_history)
    logger.debug(f"Built prompt with {len(chunks)} chunks")

    try:
        client = _get_client()
        response = await client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        answer = response.content[0].text  # type: ignore

        logger.info(f"Answer length: {len(answer)} characters")
        return answer

    except APIStatusError as e:
        # Check for 529 Overloaded code
        if e.status_code == 529:
            logger.warning("Anthropic API is overloaded (HTTP 529).")
            return "I'm sorry, the AI service is currently overloaded. Please try again in a few minutes."

        # Handle other API errors
        logger.error(f"Anthropic API returned an error: {e.status_code} - {e.message}")
        return "I encountered an error communicating with the AI service. Please try again later."

    except Exception as e:
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

    try:
        client = _get_client()
        async with client.messages.stream(
            model="claude-3-haiku-20240307",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            async for token in stream.text_stream:
                if token:
                    yield token
    except APIStatusError as e:
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
        logger.error(f"Unexpected error generating streaming answer: {e}", exc_info=True)
        raise
