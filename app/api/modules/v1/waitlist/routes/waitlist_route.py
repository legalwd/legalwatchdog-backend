import logging

from fastapi import APIRouter, BackgroundTasks, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.db.database import get_db
from app.api.modules.v1.waitlist.schemas.waitlist_schema import (
    WaitlistResponse,
    WaitlistSignup,
)
from app.api.modules.v1.waitlist.service.waitlist_service import waitlist_service
from app.api.utils.response_payloads import success_response

from .docs.waitlist_docs import (
    waitlist_signup_custom_errors,
    waitlist_signup_custom_success,
    waitlist_signup_responses,
)

router = APIRouter(prefix="/waitlist", tags=["Waitlist"])
logger = logging.getLogger("app")


@router.post(
    "/signup",
    response_model=WaitlistResponse,
    status_code=status.HTTP_201_CREATED,
    responses=waitlist_signup_responses,  # type: ignore
)
async def signup_waitlist(
    signup: WaitlistSignup,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Add a user to the waitlist.

    Validates:
    - organization_email: Must be a valid, real email address (not test/dummy/disposable emails)
    - organization_name: Must contain only letters, spaces, and common punctuation (no numbers)

    Returns:
    - 201: Successfully added to waitlist

    Raises:
    - 409: Email already exists in waitlist
    - 500: Processing error occurred during signup
    """
    result = await waitlist_service.add_to_waitlist(db, signup)

    background_tasks.add_task(waitlist_service._send_confirmation_email, signup)

    return success_response(
        status.HTTP_201_CREATED,
        "Successfully added to waitlist. Confirmation email will be sent shortly.",
        data=result.model_dump(),
    )


signup_waitlist._custom_errors = waitlist_signup_custom_errors  # type: ignore
signup_waitlist._custom_success = waitlist_signup_custom_success  # type: ignore
