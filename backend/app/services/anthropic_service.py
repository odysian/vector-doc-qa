from anthropic import Anthropic, APIStatusError

from app.config import settings
from app.utils.logging_config import get_logger

logger = get_logger(__name__)


def _build_prompt(query: str, chunks: list[dict]) -> str:
    """
    Build the prompt for Claude with chunks embedded

    Args:
        query: User's question
        chunks: Search results with content
    Returns:
        Formatted prompt string
    """

    excerpts = []
    for i, chunk in enumerate(chunks, 1):
        excerpt = f"Excerpt {i}:\n{chunk['content']}"
        excerpts.append(excerpt)

    excerpts_text = "\n\n".join(excerpts)

    prompt = f"""Here are excerpts from a document:

{excerpts_text}

Question: {query}

You are a helpful assistant. Answer the user's question using only the provided excerpts.

If the specific answer is not explicitly stated, synthesize relevant details from the text that address the core of the user's inquiry.

If the excerpts contain absolutely no relevant information, state that you cannot answer based on the provided text."""

    return prompt


def generate_answer(query: str, chunks: list[dict]) -> str:
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

    logger.info(f"Generating answer for query: '{query}'")

    prompt = _build_prompt(query, chunks)
    logger.debug(f"Built prompt with {len(chunks)} chunks")

    try:
        client = Anthropic(api_key=settings.anthropic_api_key)
        response = client.messages.create(
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
