from fastapi import HTTPException, Query, status

from app.api.core.config import settings


async def verify_admin_email(
    admin_email: str = Query(..., description="Admin email for restricted access"),
):
    if admin_email != settings.ADMIN_EMAIL:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to access this resource.",
        )
    return admin_email
