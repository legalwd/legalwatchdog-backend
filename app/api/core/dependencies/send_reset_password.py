import logging

from app.api.core.config import settings
from app.api.core.dependencies.send_mail import send_email
from app.api.core.logger import setup_logging

setup_logging()
logger = logging.getLogger("app")


async def send_password_reset_email(context: dict):
    """
    Send password reset email using the shared send_email utility.

    Args:
        context (dict): Dictionary with:
            - user_email (str): Recipient email address
            - user_name (str): User's name
            - reset_code (str): 6-digit reset code
            - frontend_url (str, optional): Frontend URL for reset link
            - app_url (str, optional): App URL for branding
            - expiry_minutes (int, optional): Expiry time in minutes

    Returns:
        bool: True if email sent successfully, False otherwise.

    Raises:
        None

    Examples:
        >>> await send_password_reset_email({
        ...     "user_email": "user@example.com",
        ...     "user_name": "John Doe",
        ...     "reset_code": "123456"
        ... })
        True
    """

    recipient = context.get("user_email")
    user_name = context.get("user_name")
    reset_code = context.get("reset_code")

    subject = "Password Reset Request - Legal Watchdog"
    template_name = "reset_password.html"

    frontend_url = context.get("frontend_url") or settings.APP_URL or settings.DEV_URL

    template_context = {
        "subject": subject,
        "user_name": user_name,
        "reset_code": reset_code,
        "frontend_url": frontend_url,
        "app_url": context.get("app_url", settings.APP_URL),
        "expiry_minutes": context.get("expiry_minutes", 15),
    }

    logger.info(f"Attempting to send password reset email to {recipient}")

    success = await send_email(
        template_name=template_name,
        subject=subject,
        recipient=recipient,
        context=template_context,
    )

    if success:
        logger.info(f"Password reset email successfully sent to {recipient}")
    else:
        logger.error(f"Failed to send password reset email to {recipient}")

    return success
