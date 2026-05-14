import logging
from typing import Optional

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    Query,
    Request,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.core.dependencies.admin_check_email import verify_admin_email
from app.api.db.database import get_db
from app.api.modules.v1.contact_us.routes.docs.contact_route import (
    contact_us_custom_errors,
    contact_us_custom_success,
    contact_us_responses,
    get_all_contacts_custom_errors,
    get_all_contacts_custom_success,
    get_all_contacts_responses,
    request_demo_custom_errors,
    request_demo_custom_success,
    request_demo_responses,
)
from app.api.modules.v1.contact_us.schemas.contact_us import (
    ContactUsListResponse,
    ContactUsRequest,
    ContactUsResponse,
    RequestDemoPayload,
    RequestDemoResponse,
)
from app.api.modules.v1.contact_us.service.contact_us import ContactUsService
from app.api.utils.response_payloads import (
    success_response,
)

router = APIRouter(prefix="/contact-us", tags=["Contact Us"])

logger = logging.getLogger("app")


@router.post(
    "",
    response_model=ContactUsResponse,
    status_code=status.HTTP_200_OK,
    responses=contact_us_responses,
)
async def contact_us(
    payload: ContactUsRequest,
    background_tasks: BackgroundTasks,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Submit a contact form.

    Processes contact form submissions and sends notification emails
    to both the admin team and the user who submitted the form.

    Rate Limited: 3 submissions per hour per email address and IP address.

    Args:
        payload (ContactUsRequest): Contact form data including full name,
            phone number, email, and message.
        background_tasks (BackgroundTasks): FastAPI background tasks instance
            for async email operations.
        request (Request): FastAPI request object for rate limiting.

    Returns:
        dict: Standardized success or error response with status, message,
            and data/error details.
    """
    ip_address: Optional[str] = request.client.host if request.client else None

    service = ContactUsService(db)
    result = await service.submit_contact_form(
        payload=payload,
        background_tasks=background_tasks,
        ip_address=ip_address,
    )

    return success_response(
        status_code=status.HTTP_200_OK,
        message="Thank you for contacting us. We'll get back to you soon!",
        data=result,
    )


contact_us._custom_errors = contact_us_custom_errors
contact_us._custom_success = contact_us_custom_success


@router.post(
    "/request-demo",
    response_model=RequestDemoResponse,
    status_code=status.HTTP_201_CREATED,
    responses=request_demo_responses,
)
async def contact_us_request_demo(
    payload: RequestDemoPayload,
    background_tasks: BackgroundTasks,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Submit a request-a-demo form.

    Persists the demo request, applies rate limiting, and sends notification emails
    to both the organization demo inbox and the prospect.
    """

    ip_address: Optional[str] = request.client.host if request.client else None

    service = ContactUsService(db)
    demo_request = await service.submit_request_demo(
        payload=payload,
        background_tasks=background_tasks,
        ip_address=ip_address,
    )

    return success_response(
        status_code=status.HTTP_201_CREATED,
        message="Demo request submitted. Our team will reach out shortly.",
        data=demo_request.model_dump(),
    )


contact_us_request_demo._custom_errors = request_demo_custom_errors
contact_us_request_demo._custom_success = request_demo_custom_success


@router.get(
    "",
    response_model=ContactUsListResponse,
    status_code=status.HTTP_200_OK,
    responses=get_all_contacts_responses,
)
async def get_all_contact_submissions(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Number of items per page"),
    email: Optional[str] = Query(None, description="Filter by email address"),
    admin_email: str = Depends(verify_admin_email),
    db: AsyncSession = Depends(get_db),
):
    """
    Get all contact form submissions with pagination.

    Retrieves a paginated list of all contact form submissions.
    Optionally filter by email address.

    **Args:**

        - page (int)
          Page number (default: 1)

        - page_size (int)
          Number of items per page (default: 10, max: 100)

        - email (str, optional)
          Filter by email address

        - admin_email (required)
          Email used to verify that you are authorized (admin-only)

        - db (AsyncSession)
          Database session

    **Returns:**
        Paginated list of contact submissions with metadata.

    **Raises:**
        500: Database operation failed.
    """
    service = ContactUsService(db)
    result = await service.get_all_contacts(
        page=page,
        page_size=page_size,
        email=email,
    )

    contacts_list = [contact.model_dump() for contact in result["data"]]

    return success_response(
        status_code=status.HTTP_200_OK,
        message="Contact submissions retrieved successfully",
        data=ContactUsListResponse(
            contacts=contacts_list,
            total=result["total"],
            page=result["page"],
            limit=result["limit"],
            total_pages=result["total_pages"],
        ).model_dump(),
    )


get_all_contact_submissions._custom_errors = get_all_contacts_custom_errors
get_all_contact_submissions._custom_success = get_all_contacts_custom_success
