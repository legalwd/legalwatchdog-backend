import hashlib
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.core.config import settings
from app.api.core.dependencies.send_mail import send_email
from app.api.core.logger import setup_logging
from app.api.modules.v1.api_access.models.api_key_token import APIKeyOnboardingToken

setup_logging()
logger = logging.getLogger("app")


async def send_api_key_email(api_key, onboarding_token: APIKeyOnboardingToken, db: AsyncSession):
    """
    Sends an API key onboarding email to the appropriate
    recipient (internal or external).

    Args:
       api_key (APIKey): The APIKey instance for which
       the onboarding email is being sent.
       onboarding_token (APIKeyOnboardingToken): The onboarding token
       instance linked to the API key.
       db (AsyncSession): The async database session (if needed
       for logging or future operations).

    Returns:
       bool: True if the email was sent successfully, False otherwise.

    Raises:
       ValueError: If the API key has neither a `user_id` nor a `receiver_email`.
    """

    if api_key.user_id:
        recipient_email = api_key.user.email
        user_name = api_key.user.name or "there"
    elif api_key.receiver_email:
        recipient_email = api_key.receiver_email
        user_name = "there"
    else:
        raise ValueError("API key has neither user_id nor receiver_email.")

    base = settings.API_KEY_FRONTEND_URL
    if not base.startswith("http"):
        base = f"https://{base}"
    onboarding_url = f"{base.rstrip('/')}/?t={onboarding_token.token}"

    template_context = {
        "user_name": user_name,
        "organization_name": api_key.organization.name,
        "onboarding_url": onboarding_url,
    }

    subject = f"Your API Key from {api_key.organization.name}"
    template_name = "api_key_invitation.html"

    logger.info(f"Attempting to send API key email to {recipient_email}")

    success = await send_email(
        template_name=template_name,
        subject=subject,
        recipient=recipient_email,
        context=template_context,
    )

    if success:
        logger.info(f"API key email successfully sent to {recipient_email}")
    else:
        logger.error(f"Failed to send API key email to {recipient_email}")

    return success


def hash_api_key(raw_key: str) -> str:
    """
    Hash API keys using SHA-256 (fast, constant-time, no salt required).

    Args:
        raw_key (str): The plaintext API key.

    Returns:
        str: Hex-encoded SHA-256 hash.
    """
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
