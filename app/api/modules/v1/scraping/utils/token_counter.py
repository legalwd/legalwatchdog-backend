"""Token counting utility for LLM context management."""

import logging

logger = logging.getLogger(__name__)


def estimate_tokens(text: str) -> int:
    """Estimate token count for text using character-based heuristic.

    Uses industry-standard approximation: 1 token ≈ 4 characters for English text.
    This is a fast approximation suitable for context overflow prevention.

    For exact token counts, use tiktoken library (OpenAI's tokenizer), but this
    adds dependency overhead. Character-based estimation is sufficient for safety checks.

    Args:
        text (str): Input text to estimate tokens for.

    Returns:
        int: Estimated token count.

    Examples:
        >>> estimate_tokens("Hello world")
        3  # ~11 chars / 4 = 2.75 ≈ 3 tokens
        >>> estimate_tokens("A" * 1000)
        250  # 1000 chars / 4 = 250 tokens
    """
    if not text:
        return 0

    return len(text) // 4


def truncate_to_token_limit(
    text: str, max_tokens: int, preserve_start: bool = True
) -> tuple[str, bool]:
    """Truncate text to fit within token limit.

    Args:
        text (str): Input text to truncate.
        max_tokens (int): Maximum allowed tokens.
        preserve_start (bool): If True, keep beginning of text. If False, keep end.

    Returns:
        tuple[str, bool]: (truncated_text, was_truncated)

    Examples:
        >>> text = "A" * 1000
        >>> truncated, was_cut = truncate_to_token_limit(text, 100)
        >>> estimate_tokens(truncated)
        100
        >>> was_cut
        True
    """
    current_tokens = estimate_tokens(text)

    if current_tokens <= max_tokens:
        return text, False

    char_limit = max_tokens * 4

    if preserve_start:
        truncated = text[:char_limit]
    else:
        truncated = text[-char_limit:]

    logger.warning(
        f"Text truncated from {current_tokens} to ~{max_tokens} tokens "
        f"({len(text)} to {len(truncated)} chars)"
    )

    return truncated, True
