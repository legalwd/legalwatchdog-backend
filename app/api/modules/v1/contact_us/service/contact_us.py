import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.core.config import settings
from app.api.core.custom_exceptions.exceptions import (
    ProcessingError,
    RateLimitExceededError,
    ValidationError,
)
from app.api.core.dependencies.redis_service import check_rate_limit
from app.api.core.dependencies.send_mail import send_email
from app.api.modules.v1.contact_us.schemas.contact_us import (
    ContactUsDetail,
    ContactUsRequest,
    RequestDemoPayload,
    RequestDemoResponse,
)
from app.api.modules.v1.contact_us.service.contact_us_repository import (
    ContactUsCRUD,
    DemoRequestCRUD,
)
from app.api.utils.pagination import calculate_pagination

logger = logging.getLogger("app")


class ContactUsService:
    """
    Service class to handle contact us logic.

    """

    MAX_CONTACT_ATTEMPTS = 3
    RATE_LIMIT_WINDOW_SECONDS = 3600
    IP_RATE_LIMIT_MULTIPLIER = 2

    def __init__(self, db: AsyncSession):
        """
        Initialize contact us service.

        """

        self.db = db

    async def submit_contact_form(
        self,
        payload: ContactUsRequest,
        background_tasks: BackgroundTasks,
        ip_address: Optional[str] = None,
    ) -> dict:
        """
        Handle contact form submission.

        This method processes the contact form, sends notification emails

        Args:
            payload: Contact form data containing name, email, phone, and message
            background_tasks: FastAPI background tasks for async email sending
            ip_address: Optional IP address for rate limiting

        Returns:
            dict: Dictionary containing the submitted email address

        Raises:
            ValidationError: For validation errors
            RateLimitExceededError: If rate limit is exceeded
            ProcessingError: For unexpected errors during submission process
        """
        try:
            logger.info("Processing contact form submission from email=%s", payload.email)

            # Rate limiting
            email_allowed = await check_rate_limit(
                f"contact:email:{payload.email}",
                max_attempts=self.MAX_CONTACT_ATTEMPTS,
                window_seconds=self.RATE_LIMIT_WINDOW_SECONDS,
            )

            if not email_allowed:
                logger.warning(f"Rate limit exceeded for email: {payload.email}")
                raise RateLimitExceededError(
                    message="Too many contact form submissions. Please try again in 1 hour."
                )

            if ip_address:
                ip_allowed = await check_rate_limit(
                    f"contact:ip:{ip_address}",
                    max_attempts=self.MAX_CONTACT_ATTEMPTS * self.IP_RATE_LIMIT_MULTIPLIER,
                    window_seconds=self.RATE_LIMIT_WINDOW_SECONDS,
                )

                if not ip_allowed:
                    logger.warning(f"Rate limit exceeded for IP: {ip_address}")
                    raise RateLimitExceededError(
                        message="Too many attempts from this IP. Try again in 1 hour."
                    )

            admin_context = {
                "full_name": payload.full_name,
                "email": payload.email,
                "phone_number": payload.phone_number,
                "message": payload.message,
                "submitted_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
            }

            background_tasks.add_task(
                send_email,
                "contact_us_admin.html",
                f"New Contact Form Submission from {payload.full_name}",
                settings.ADMIN_EMAIL,
                admin_context,
            )

            user_context = {
                "full_name": payload.full_name,
                "message": payload.message,
            }

            background_tasks.add_task(
                send_email,
                "contact_us_confirmation.html",
                "We received your message",
                payload.email,
                user_context,
            )

            logger.info("Successfully processed contact form from email=%s", payload.email)

            await ContactUsCRUD.create(
                db=self.db,
                full_name=payload.full_name,
                email=payload.email,
                phone_number=payload.phone_number,
                message=payload.message,
            )

            await self.db.commit()

            return {"email": payload.email}

        except ValueError as e:
            logger.warning("Contact form validation failed for email=%s: %s", payload.email, str(e))
            await self.db.rollback()
            raise ValidationError(message=str(e))

        except Exception as e:
            logger.error(
                "Failed to process contact form for email=%s: %s",
                payload.email,
                str(e),
                exc_info=True,
            )
            await self.db.rollback()
            raise ProcessingError(
                message="Failed to submit your message. Please try again later."
            ) from e

    async def submit_request_demo(
        self,
        payload: RequestDemoPayload,
        background_tasks: BackgroundTasks,
        ip_address: Optional[str] = None,
    ) -> RequestDemoResponse:
        """Handle demo request submission.

        Persists the demo request and schedules notification emails.

        Raises domain ValidationError for semantic validation issues and
        ProcessingError for controlled processing failures.
        """
        try:
            logger.info("Processing demo request from work_email=%s", payload.work_email)

            # Rate limiting
            email_allowed = await check_rate_limit(
                f"request-demo:email:{payload.work_email}",
                max_attempts=self.MAX_CONTACT_ATTEMPTS,
                window_seconds=self.RATE_LIMIT_WINDOW_SECONDS,
            )

            if not email_allowed:
                logger.warning("Demo request rate limit exceeded for email: %s", payload.work_email)
                raise RateLimitExceededError(
                    message="Too many demo requests. Please try again in 1 hour."
                )

            if ip_address:
                ip_allowed = await check_rate_limit(
                    f"request-demo:ip:{ip_address}",
                    max_attempts=self.MAX_CONTACT_ATTEMPTS * self.IP_RATE_LIMIT_MULTIPLIER,
                    window_seconds=self.RATE_LIMIT_WINDOW_SECONDS,
                )

                if not ip_allowed:
                    logger.warning("Demo request rate limit exceeded for IP: %s", ip_address)
                    raise RateLimitExceededError(
                        message="Too many attempts from this IP. Try again in 1 hour."
                    )

            demo_request = await DemoRequestCRUD.create(
                db=self.db,
                first_name=payload.first_name.strip(),
                last_name=payload.last_name.strip(),
                company_name=payload.company_name.strip(),
                company_size=payload.company_size,
                industry=payload.industry.strip(),
                company_website_url=str(payload.company_website_url),
                country=payload.country.strip(),
                work_email=str(payload.work_email),
                job_title=payload.job_title.strip() if payload.job_title else None,
                additional_context=payload.additional_context.strip()
                if payload.additional_context
                else None,
            )

            admin_context = {
                "first_name": demo_request.first_name,
                "last_name": demo_request.last_name,
                "company_name": demo_request.company_name,
                "company_size": demo_request.company_size,
                "industry": demo_request.industry,
                "company_website_url": demo_request.company_website_url,
                "country": demo_request.country,
                "work_email": demo_request.work_email,
                "job_title": demo_request.job_title,
                "additional_context": demo_request.additional_context,
                "requested_at": demo_request.created_at.strftime("%Y-%m-%d %H:%M:%S UTC"),
            }

            background_tasks.add_task(
                send_email,
                "request_demo_admin.html",
                f"New demo request from {demo_request.first_name} {demo_request.last_name}",
                settings.DEMO_REQUEST_NOTIFICATION_EMAIL,
                admin_context,
            )

            user_context = {
                "first_name": demo_request.first_name,
                "last_name": demo_request.last_name,
                "company_name": demo_request.company_name,
            }

            background_tasks.add_task(
                send_email,
                "request_demo_confirmation.html",
                "We received your demo request",
                demo_request.work_email,
                user_context,
            )

            await self.db.commit()

            return RequestDemoResponse.model_validate(demo_request)

        except (ValidationError, ProcessingError, RateLimitExceededError):
            await self.db.rollback()
            raise

        except ValueError as e:
            logger.warning(
                "Demo request validation failed for work_email=%s: %s",
                payload.work_email,
                str(e),
            )
            await self.db.rollback()
            raise ValidationError(message=str(e))

        except Exception as e:
            logger.error(
                "Failed to process demo request for email=%s: %s",
                payload.work_email,
                str(e),
                exc_info=True,
            )
            await self.db.rollback()
            raise ProcessingError(
                message="Failed to submit your demo request. Please try again later."
            ) from e

    async def get_all_contacts(
        self,
        page: int,
        page_size: int,
        email: Optional[str] = None,
    ) -> dict:
        """
        Get all contact submissions with pagination.

        Args:
            page: Page number (1-indexed)
            page_size: Number of items per page
            email: Optional email filter

        Returns:
            dict: Dictionary with contacts list and pagination metadata

        Raises:
            ProcessingError: For unexpected errors during retrieval
        """

        try:
            contacts, total_count = await ContactUsCRUD.get_all(
                db=self.db,
                page=page,
                page_size=page_size,
                email=email,
            )

            contacts_list = [ContactUsDetail.model_validate(contact) for contact in contacts]

            pagination = calculate_pagination(
                total=total_count,
                page=page,
                limit=page_size,
            )

            return {"data": contacts_list, **pagination}

        except Exception as e:
            logger.error(
                "Failed to retrieve contact submissions: %s",
                str(e),
                exc_info=True,
            )
            raise ProcessingError(message="Failed to retrieve contact submissions") from e
