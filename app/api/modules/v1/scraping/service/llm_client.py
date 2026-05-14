import logging

from google import genai

from app.api.core.config import settings

logger = logging.getLogger(__name__)


class LLMClient:
    """
    Client for interacting with LLM providers with generic data extraction capabilities.
    Supports multiple LLM providers through environment configuration.
    """

    def __init__(self):
        """Initialize LLM client with configuration from settings."""
        self.api_key = settings.LLM_API_KEY
        if not self.api_key:
            raise ValueError("LLM_API_KEY not set in environment")
        self.client = genai.Client(api_key=self.api_key)
        logger.info("LLM client initialized successfully")

    def ask(self, user_message: str) -> str:
        """
        Send a message to the LLM and return the response.

        Args:
            user_message: The prompt message to send to the LLM

        Returns:
            The LLM response as a string, or error message if request fails
        """
        try:
            response = self.client.models.generate_content(
                model=settings.LLM_MODEL,
                contents=[user_message],
                config={
                    "system_instruction": settings.LLM_SYSTEM_PROMPT,
                    "temperature": settings.LLM_TEMPERATURE,
                    "max_output_tokens": settings.LLM_MAX_TOKENS,
                },
            )
            if hasattr(response, "text"):
                return response.text.strip()
            elif hasattr(response, "candidates") and response.candidates:
                return response.candidates[0].content.parts[0].text.strip()
            else:
                return str(response)
        except Exception as e:
            logger.error(f"LLM request failed: {e}")
            return f"Error: {e}"
