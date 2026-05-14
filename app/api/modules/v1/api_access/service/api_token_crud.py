from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.modules.v1.api_access.models.api_key_token import APIKeyOnboardingToken


async def create_api_key_onboarding_token(
    api_key, db: AsyncSession, expires_in_hours: int = 24
) -> APIKeyOnboardingToken:
    """
    Create a new onboarding token for the API key and save it in the database.

    Args:
        api_key: The APIKey instance this token is for.
        db (AsyncSession): The async database session.
        expires_in_hours (int, optional): Token expiry in hours. Defaults to 24.

    Returns:
        APIKeyOnboardingToken: The newly created onboarding token instance.
    """
    token = APIKeyOnboardingToken(
        api_key_id=api_key.id,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=expires_in_hours),
        token=str(uuid4()),
    )
    db.add(token)
    await db.commit()
    await db.refresh(token)
    return token
