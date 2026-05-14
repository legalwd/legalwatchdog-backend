import logging

logger = logging.getLogger(__name__)


async def build_final_prompt(project_prompt: str, jurisdiction_prompt: str) -> str:
    """
    Combine project and jurisdiction prompts into a single instruction set.

    Args:
        project_prompt: Main project instructions and objectives
        jurisdiction_prompt: Additional context for specific jurisdiction

    Returns:
        Combined prompt string ready for LLM processing
    """
    logger.info("PromptService: Building combined LLM prompt")

    combined_prompt = f"{project_prompt}\n{jurisdiction_prompt}".strip()

    final_prompt = f"""
Instructions from project + jurisdiction:
{combined_prompt}

Use ONLY the scraped data that will be appended after this prompt to complete the task.
Follow instructions strictly.
"""

    logger.info("PromptService: Final LLM prompt successfully built.")
    return final_prompt.strip()
