import logging
import uuid
from typing import Optional, Tuple

from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.api.modules.v1.contact_us.models.contact_us_model import ContactUs
from app.api.modules.v1.contact_us.models.demo_request_model import DemoRequest

logger = logging.getLogger("app")


class ContactUsCRUD:
    """CRUD operations for ContactUs model."""

    @staticmethod
    async def create(
        db: AsyncSession,
        full_name: str,
        email: str,
        phone_number: str,
        message: str,
    ) -> ContactUs:
        """
        Create a new contact us submission in the database.

        Args:
            db: Async database session
            full_name: User's full name
            email: User's email address
            phone_number: User's phone number
            message: User's message

        Returns:
            ContactUs: Created contact us object

        Raises:
            Exception: If database operation fails
        """
        try:
            contact_submission = ContactUs(
                full_name=full_name,
                email=email,
                phone_number=phone_number,
                message=message,
            )

            db.add(contact_submission)
            await db.flush()
            await db.refresh(contact_submission)

            logger.info(
                "Created contact submission: id=%s, email=%s",
                contact_submission.id,
                contact_submission.email,
            )

            return contact_submission

        except Exception as e:
            logger.error(
                "Failed to create contact submission for email=%s: %s",
                email,
                str(e),
                exc_info=True,
            )
            raise Exception(
                "We're unable to submit your message at this time. "
                "Please try again later or email us directly."
            )

    @staticmethod
    async def get_by_id(db: AsyncSession, contact_id: uuid.UUID) -> Optional[ContactUs]:
        """
        Get contact submission by ID.

        Args:
            db: Database session
            contact_id: Contact submission UUID

        Returns:
            ContactUs or None if not found
        """
        result = await db.execute(select(ContactUs).where(ContactUs.id == contact_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_email(db: AsyncSession, email: str, limit: int = 10) -> list[ContactUs]:
        """
        Get contact submissions by email address.

        Args:
            db: Database session
            email: Email address
            limit: Maximum number of results

        Returns:
            List of ContactUs objects
        """
        result = await db.execute(
            select(ContactUs)
            .where(ContactUs.email == email)
            .order_by(ContactUs.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_all(
        db: AsyncSession,
        page: int,
        page_size: int,
        email: Optional[str] = None,
    ) -> Tuple[list[ContactUs], int]:
        """
        Get all contact submissions with pagination.

        Args:
            db: Database session
            page: Page number (1-indexed)
            page_size: Number of items per page
            email: Optional email filter

        Returns:
            Tuple of (list of ContactUs objects, total count)
        """
        try:
            query = select(ContactUs)
            count_query = select(func.count()).select_from(ContactUs)

            if email:
                query = query.where(ContactUs.email == email)
                count_query = count_query.where(ContactUs.email == email)

            total_result = await db.execute(count_query)
            total_count = total_result.scalar_one()

            offset = (page - 1) * page_size
            query = query.order_by(ContactUs.created_at.desc()).offset(offset).limit(page_size)

            result = await db.execute(query)
            contacts = list(result.scalars().all())

            logger.info(
                "Retrieved %d contact submissions (page=%d, page_size=%d, total=%d)",
                len(contacts),
                page,
                page_size,
                total_count,
            )

            return contacts, total_count

        except Exception as e:
            logger.error(
                "Failed to retrieve paginated contact submissions: %s",
                str(e),
                exc_info=True,
            )
            raise


class DemoRequestCRUD:
    """CRUD operations for DemoRequest model."""

    @staticmethod
    async def create(
        db: AsyncSession,
        *,
        first_name: str,
        last_name: str,
        company_name: str,
        company_size: str,
        industry: str,
        company_website_url: str,
        country: str,
        work_email: str,
        job_title: str | None = None,
        additional_context: str | None = None,
    ) -> DemoRequest:
        """Create a new demo request submission in the database."""

        try:
            demo_request = DemoRequest(
                first_name=first_name,
                last_name=last_name,
                company_name=company_name,
                company_size=company_size,
                industry=industry,
                company_website_url=company_website_url,
                country=country,
                work_email=work_email,
                job_title=job_title,
                additional_context=additional_context,
            )

            db.add(demo_request)
            await db.flush()
            await db.refresh(demo_request)

            logger.info(
                "Created demo request: id=%s, email=%s",
                demo_request.id,
                demo_request.work_email,
            )

            return demo_request

        except Exception as e:
            logger.error(
                "Failed to create demo request for email=%s: %s",
                work_email,
                str(e),
                exc_info=True,
            )
            raise
