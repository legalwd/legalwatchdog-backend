import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import func, select

from app.api.modules.v1.organization.models.organization_model import CompanySize, Organization

logger = logging.getLogger("app")


class OrganizationCRUD:
    """CRUD operations for Organization model."""

    @staticmethod
    async def create_organization(
        db: AsyncSession,
        name: str,
        industry: Optional[str] = None,
        country: Optional[str] = None,
        email: Optional[str] = None,
        company_size: Optional[CompanySize] = None,
        org_type: Optional[str] = None,
    ) -> Organization:
        """
        Create a new organization in the database.

        Args:
            db: Async database session
            name: Organization name
            industry: Industry type (optional)

        Returns:
            Organization: Created organization object

        Raises:
            Exception: If database operation fails
        """
        try:
            organization = Organization(
                name=name,
                industry=industry,
                country=country,
                email=email,
                company_size=company_size,
                org_type=org_type,
                is_active=True,
            )

            db.add(organization)
            await db.flush()
            await db.refresh(organization)

            logger.info("Created organization: id=%s, name=%s", organization.id, organization.name)

            return organization

        except Exception as e:
            logger.error(
                "Failed to create organization with name=%s: %s", name, str(e), exc_info=True
            )
            raise Exception("Failed to create organization")

    @staticmethod
    async def get_by_id(db: AsyncSession, organization_id: uuid.UUID) -> Optional[Organization]:
        """
        Get organization by ID.

        Args:
            db: Database session
            organization_id: Organization UUID

        Returns:
            Organization or None if not found
        """
        result = await db.execute(
            select(Organization).where(
                Organization.id == organization_id, Organization.deleted_at.is_(None)
            )
        )
        organization = result.scalar_one_or_none()

        if organization:
            logger.info(f"org {organization_id}:{organization.name},del{organization.deleted_at}")
        else:
            logger.info(f"no org {organization_id}")

        return organization

    @staticmethod
    async def get_by_name(db: AsyncSession, name: str) -> Optional[Organization]:
        """
        Get organization by name.

        Args:
            db: Database session
            name: Organization name

        Returns:
            Organization or None if not found
        """
        result = await db.execute(
            select(Organization).where(
                Organization.deleted_at.is_(None),
                func.lower(Organization.name) == func.lower(name),
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def update(
        db: AsyncSession,
        organization_id: uuid.UUID,
        name: str | None = None,
        industry: str | None = None,
        country: str | None = None,
        email: str | None = None,
        company_size: CompanySize | None = None,
        org_type: str | None = None,
        is_active: bool | None = None,
    ) -> Organization:
        """
        Update organization details.

        Args:
            db: Database session
            organization_id: Organization UUID
            name: Optional new organization name
            industry: Optional new industry
            is_active: Optional new active status

        Returns:
            Organization: Updated organization object

        Raises:
            Exception: If database operation fails
        """
        from datetime import datetime, timezone

        try:
            result = await db.execute(
                select(Organization).where(Organization.id == organization_id)
            )
            organization = result.scalar_one_or_none()

            if not organization:
                raise ValueError("Organization not found")

            if name is not None:
                organization.name = name
            if industry is not None:
                organization.industry = industry
            if country is not None:
                organization.country = country
            if email is not None:
                organization.email = email
            if company_size is not None:
                organization.company_size = company_size
            if org_type is not None:
                organization.org_type = org_type
            if is_active is not None:
                organization.is_active = is_active

            organization.updated_at = datetime.now(timezone.utc)

            await db.flush()
            await db.refresh(organization)

            logger.info("Updated organization: id=%s, name=%s", organization.id, organization.name)

            return organization

        except ValueError:
            raise
        except Exception as e:
            logger.error(
                "Failed to update organization with id=%s: %s",
                organization_id,
                str(e),
                exc_info=True,
            )
            raise Exception("Failed to update organization")

    @staticmethod
    async def get_user_org_by_name(
        db: AsyncSession, user_id: uuid.UUID, name: str
    ) -> Optional[Organization]:
        """
        Get an organization by name belonging to a specific user.
        """
        from app.api.modules.v1.organization.service.user_organization_service import (
            UserOrganizationCRUD,
        )

        memberships = await UserOrganizationCRUD.get_user_organizations(db, user_id)

        if not memberships:
            return None

        org_ids = [m.organization_id for m in memberships]

        if not org_ids:
            return None

        stmt = select(Organization).where(
            Organization.id.in_(org_ids),
            Organization.deleted_at.is_(None),
            func.lower(Organization.name) == func.lower(name),
        )
        result = await db.execute(stmt)

        return result.scalar_one_or_none()

    @staticmethod
    async def delete_organization(
        db: AsyncSession,
        organization_id: uuid.UUID,
    ) -> dict:
        """
        Delete an organization and all its associated data.

        Args:
            db: Database session
            organization_id: Organization UUID to delete

        Returns:
            dict: Dictionary with deletion confirmation

        Raises:
            Exception: If database operation fails
        """
        try:
            organization = await OrganizationCRUD.get_by_id(db, organization_id)
            if not organization:
                raise ValueError("Organization not found")

            logger.info(
                "Deleting organization: id=%s, name=%s",
                organization.id,
                organization.name,
            )

            organization.deleted_at = datetime.now(timezone.utc)
            organization.is_active = False
            await db.flush()

            logger.info(
                "Successfully deleted organization: id=%s, name=%s",
                organization_id,
                organization.name,
            )

            return {
                "organization_id": str(organization_id),
                "organization_name": organization.name,
                "deleted_at": organization.deleted_at.isoformat(),
            }

        except Exception as e:
            logger.error(
                "Failed to delete organization with id=%s: %s",
                organization_id,
                str(e),
                exc_info=True,
            )
            raise Exception("Failed to delete organization")
