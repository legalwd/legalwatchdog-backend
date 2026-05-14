"""Service for superadmin organization management operations."""

import csv
import io
import json
import logging
from datetime import datetime
from typing import Generator, Optional

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.api.core.custom_exceptions.exceptions import (
    InvalidOrganizationFilterError,
    OrganizationDataRetrievalError,
    OrganizationExportError,
)
from app.api.modules.v1.organization.models.organization_model import (
    CompanySize,
    Organization,
)
from app.api.modules.v1.organization.models.user_organization_model import UserOrganization
from app.api.modules.v1.users.models.roles_model import Role
from app.api.modules.v1.users.models.users_model import User
from app.api.utils.pagination import calculate_pagination

logger = logging.getLogger(__name__)

VALID_SORT_FIELDS = ["created_at", "updated_at", "name", "owner_email", "owner_created_at"]
VALID_SORT_ORDERS = ["asc", "desc"]


class OrganizationManagementService:
    """Service handling superadmin organization management operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_organizations(
        self,
        page: int = 1,
        limit: int = 20,
        is_approved: Optional[bool] = None,
        is_active: Optional[bool] = None,
        company_size: Optional[str] = None,
        industry: Optional[str] = None,
        search: Optional[str] = None,
        created_from: Optional[datetime] = None,
        created_to: Optional[datetime] = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> dict:
        """
        List all organizations with owner details, pagination and filtering.

        Args:
            page: Page number (1-indexed)
            limit: Items per page
            is_approved: Filter by owner approval status
            is_active: Filter by organization active status
            company_size: Filter by company size (e.g., "1-50", "51-200")
            industry: Filter by industry type
            search: Search in organization name, email, or owner name/email
            created_from: Filter organizations created after this date (ISO format)
            created_to: Filter organizations created before this date (ISO format)
            sort_by: Sort field (created_at, updated_at, name, owner_email, owner_created_at)
            sort_order: Sort order (asc or desc)

        Returns:
            Dictionary with organizations list, pagination metadata, and total count

        Raises:
            InvalidCustomerFilterError: If invalid filter parameters provided
            CustomerDataRetrievalError: If data retrieval fails
        """
        try:
            self._validate_filters(sort_by, sort_order, company_size)

            OwnerUser = aliased(User)
            OwnerRole = aliased(Role)
            OwnerMembership = aliased(UserOrganization)

            owner_subquery = (
                select(
                    OwnerMembership.organization_id,
                    OwnerUser.id.label("owner_id"),
                    OwnerUser.name.label("owner_name"),
                    OwnerUser.email.label("owner_email"),
                    OwnerUser.is_approved.label("owner_is_approved"),
                    OwnerUser.is_active.label("owner_is_active"),
                    OwnerUser.is_verified.label("owner_is_verified"),
                    OwnerUser.approved_at.label("owner_approved_at"),
                    OwnerUser.created_at.label("owner_created_at"),
                    OwnerUser.last_login.label("owner_last_login"),
                    OwnerUser.last_active.label("owner_last_active"),
                )
                .join(OwnerUser, OwnerMembership.user_id == OwnerUser.id)
                .join(OwnerRole, OwnerMembership.role_id == OwnerRole.id)
                .where(
                    OwnerMembership.is_deleted.is_(False),
                    OwnerMembership.is_active.is_(True),
                    OwnerRole.name == "Owner",
                )
                .subquery()
            )

            query = (
                select(
                    Organization,
                    owner_subquery.c.owner_id,
                    owner_subquery.c.owner_name,
                    owner_subquery.c.owner_email,
                    owner_subquery.c.owner_is_approved,
                    owner_subquery.c.owner_is_active,
                    owner_subquery.c.owner_is_verified,
                    owner_subquery.c.owner_approved_at,
                    owner_subquery.c.owner_created_at,
                    owner_subquery.c.owner_last_login,
                    owner_subquery.c.owner_last_active,
                )
                .outerjoin(
                    owner_subquery,
                    Organization.id == owner_subquery.c.organization_id,
                )
                .where(Organization.deleted_at.is_(None))
            )

            count_query = (
                select(func.count(Organization.id))
                .outerjoin(
                    owner_subquery,
                    Organization.id == owner_subquery.c.organization_id,
                )
                .where(Organization.deleted_at.is_(None))
            )

            query, count_query = self._apply_filters(
                query,
                count_query,
                owner_subquery,
                is_approved=is_approved,
                is_active=is_active,
                company_size=company_size,
                industry=industry,
                search=search,
                created_from=created_from,
                created_to=created_to,
            )

            count_result = await self.db.execute(count_query)
            total = count_result.scalar() or 0

            query = self._apply_sorting(query, owner_subquery, sort_by, sort_order)

            offset = (page - 1) * limit
            query = query.offset(offset).limit(limit)

            result = await self.db.execute(query)
            rows = result.all()

            organizations_data = [self._row_to_dict(row) for row in rows]

            pagination = calculate_pagination(total, page, limit)

            return {
                "data": {"organizations": organizations_data},
                "meta": pagination,
                "total": total,
            }

        except InvalidOrganizationFilterError:
            raise
        except Exception as e:
            logger.error(f"Error listing organizations: {e}", exc_info=True)
            raise OrganizationDataRetrievalError("Failed to retrieve organizations list")

    async def get_export_data(
        self,
        is_approved: Optional[bool] = None,
        is_active: Optional[bool] = None,
        company_size: Optional[str] = None,
        industry: Optional[str] = None,
        search: Optional[str] = None,
        created_from: Optional[datetime] = None,
        created_to: Optional[datetime] = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> list[dict]:
        """
        Get all organizations matching filters for export (no pagination).

        Args:
            is_approved: Filter by owner approval status
            is_active: Filter by organization active status
            company_size: Filter by company size
            industry: Filter by industry type
            search: Search in organization name, email, or owner name/email
            created_from: Filter organizations created after this date
            created_to: Filter organizations created before this date
            sort_by: Sort field
            sort_order: Sort order

        Returns:
            List of organization dictionaries with owner details

        Raises:
            InvalidCustomerFilterError: If invalid filter parameters provided
            CustomerDataRetrievalError: If data retrieval fails
        """
        try:
            self._validate_filters(sort_by, sort_order, company_size)

            OwnerUser = aliased(User)
            OwnerRole = aliased(Role)
            OwnerMembership = aliased(UserOrganization)

            owner_subquery = (
                select(
                    OwnerMembership.organization_id,
                    OwnerUser.id.label("owner_id"),
                    OwnerUser.name.label("owner_name"),
                    OwnerUser.email.label("owner_email"),
                    OwnerUser.is_approved.label("owner_is_approved"),
                    OwnerUser.is_active.label("owner_is_active"),
                    OwnerUser.is_verified.label("owner_is_verified"),
                    OwnerUser.approved_at.label("owner_approved_at"),
                    OwnerUser.created_at.label("owner_created_at"),
                    OwnerUser.last_login.label("owner_last_login"),
                    OwnerUser.last_active.label("owner_last_active"),
                )
                .join(OwnerUser, OwnerMembership.user_id == OwnerUser.id)
                .join(OwnerRole, OwnerMembership.role_id == OwnerRole.id)
                .where(
                    OwnerMembership.is_deleted.is_(False),
                    OwnerMembership.is_active.is_(True),
                    OwnerRole.name == "Owner",
                )
                .subquery()
            )

            query = (
                select(
                    Organization,
                    owner_subquery.c.owner_id,
                    owner_subquery.c.owner_name,
                    owner_subquery.c.owner_email,
                    owner_subquery.c.owner_is_approved,
                    owner_subquery.c.owner_is_active,
                    owner_subquery.c.owner_is_verified,
                    owner_subquery.c.owner_approved_at,
                    owner_subquery.c.owner_created_at,
                    owner_subquery.c.owner_last_login,
                    owner_subquery.c.owner_last_active,
                )
                .outerjoin(
                    owner_subquery,
                    Organization.id == owner_subquery.c.organization_id,
                )
                .where(Organization.deleted_at.is_(None))
            )

            count_query = select(func.count(Organization.id)).where(
                Organization.deleted_at.is_(None)
            )

            query, _ = self._apply_filters(
                query,
                count_query,
                owner_subquery,
                is_approved=is_approved,
                is_active=is_active,
                company_size=company_size,
                industry=industry,
                search=search,
                created_from=created_from,
                created_to=created_to,
            )

            query = self._apply_sorting(query, owner_subquery, sort_by, sort_order)

            result = await self.db.execute(query)
            rows = result.all()

            return [self._row_to_dict(row) for row in rows]

        except InvalidOrganizationFilterError:
            raise
        except Exception as e:
            logger.error(f"Error getting export data: {e}", exc_info=True)
            raise OrganizationExportError("Failed to export organizations")

    def _validate_filters(self, sort_by: str, sort_order: str, company_size: Optional[str]) -> None:
        """Validate filter parameters."""
        if sort_by not in VALID_SORT_FIELDS:
            raise InvalidOrganizationFilterError(
                f"Invalid sort field: {sort_by}. Must be one of: {', '.join(VALID_SORT_FIELDS)}"
            )

        if sort_order.lower() not in VALID_SORT_ORDERS:
            raise InvalidOrganizationFilterError(
                f"Invalid sort order: {sort_order}. Must be 'asc' or 'desc'"
            )

        if company_size:
            valid_sizes = [size.value for size in CompanySize]
            if company_size not in valid_sizes:
                raise InvalidOrganizationFilterError(
                    f"Invalid company size: {company_size}. "
                    f"Must be one of: {', '.join(valid_sizes)}"
                )

    def _apply_filters(
        self,
        query,
        count_query,
        owner_subquery,
        is_approved: Optional[bool] = None,
        is_active: Optional[bool] = None,
        company_size: Optional[str] = None,
        industry: Optional[str] = None,
        search: Optional[str] = None,
        created_from: Optional[datetime] = None,
        created_to: Optional[datetime] = None,
    ):
        """Apply filters to query and count query."""
        if is_approved is not None:
            query = query.where(owner_subquery.c.owner_is_approved == is_approved)
            count_query = count_query.outerjoin(
                owner_subquery,
                Organization.id == owner_subquery.c.organization_id,
            ).where(owner_subquery.c.owner_is_approved == is_approved)

        if is_active is not None:
            query = query.where(Organization.is_active == is_active)
            count_query = count_query.where(Organization.is_active == is_active)

        if company_size:
            query = query.where(Organization.company_size == company_size)
            count_query = count_query.where(Organization.company_size == company_size)

        if industry:
            industry_pattern = f"%{industry}%"
            query = query.where(Organization.industry.ilike(industry_pattern))
            count_query = count_query.where(Organization.industry.ilike(industry_pattern))

        if search:
            search_pattern = f"%{search}%"
            search_conditions = or_(
                Organization.name.ilike(search_pattern),
                Organization.email.ilike(search_pattern),
                owner_subquery.c.owner_name.ilike(search_pattern),
                owner_subquery.c.owner_email.ilike(search_pattern),
            )
            query = query.where(search_conditions)
            count_query = count_query.outerjoin(
                owner_subquery,
                Organization.id == owner_subquery.c.organization_id,
            ).where(search_conditions)

        if created_from:
            query = query.where(Organization.created_at >= created_from)
            count_query = count_query.where(Organization.created_at >= created_from)

        if created_to:
            query = query.where(Organization.created_at <= created_to)
            count_query = count_query.where(Organization.created_at <= created_to)

        return query, count_query

    def _apply_sorting(self, query, owner_subquery, sort_by: str, sort_order: str):
        """Apply sorting to query."""
        sort_mapping = {
            "created_at": Organization.created_at,
            "updated_at": Organization.updated_at,
            "name": Organization.name,
            "owner_email": owner_subquery.c.owner_email,
            "owner_created_at": owner_subquery.c.owner_created_at,
        }

        sort_column = sort_mapping.get(sort_by, Organization.created_at)

        if sort_order.lower() == "asc":
            query = query.order_by(sort_column.asc().nullslast())
        else:
            query = query.order_by(sort_column.desc().nullslast())

        return query

    def _row_to_dict(self, row) -> dict:
        """Convert database row to dictionary with organization and owner details."""
        org = row[0]

        owner_data = None
        if row.owner_id is not None:
            owner_data = {
                "id": str(row.owner_id),
                "name": row.owner_name,
                "email": row.owner_email,
                "is_approved": row.owner_is_approved,
                "is_active": row.owner_is_active,
                "is_verified": row.owner_is_verified,
                "approved_at": (
                    row.owner_approved_at.isoformat() if row.owner_approved_at else None
                ),
                "created_at": (row.owner_created_at.isoformat() if row.owner_created_at else None),
                "last_login": (row.owner_last_login.isoformat() if row.owner_last_login else None),
                "last_active": (
                    row.owner_last_active.isoformat() if row.owner_last_active else None
                ),
            }

        return {
            "id": str(org.id),
            "name": org.name,
            "industry": org.industry,
            "location": org.location,
            "country": org.country,
            "email": org.email,
            "company_size": org.company_size.value if org.company_size else None,
            "org_type": org.org_type,
            "plan": org.plan,
            "logo_url": org.logo_url,
            "is_active": org.is_active,
            "created_at": org.created_at.isoformat() if org.created_at else None,
            "updated_at": org.updated_at.isoformat() if org.updated_at else None,
            "owner": owner_data,
        }


def generate_json_stream(data: list[dict]) -> Generator[bytes, None, None]:
    """
    Generate JSON bytes stream for export.

    Args:
        data: List of organization dictionaries

    Yields:
        JSON bytes chunks
    """
    yield b"["
    first = True
    for item in data:
        if not first:
            yield b","
        else:
            first = False
        yield json.dumps(item).encode("utf-8")
    yield b"]"


def generate_csv_stream(data: list[dict]) -> Generator[str, None, None]:
    """
    Generate CSV string stream for export.

    Args:
        data: List of organization dictionaries

    Yields:
        CSV string chunks (header row first, then data rows)
    """
    csv_headers = [
        "org_id",
        "org_name",
        "industry",
        "location",
        "country",
        "org_email",
        "company_size",
        "org_type",
        "plan",
        "is_active",
        "org_created_at",
        "org_updated_at",
        "owner_id",
        "owner_name",
        "owner_email",
        "owner_is_approved",
        "owner_is_active",
        "owner_is_verified",
        "owner_approved_at",
        "owner_created_at",
        "owner_last_login",
        "owner_last_active",
    ]

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(csv_headers)
    yield output.getvalue()
    output.seek(0)
    output.truncate(0)

    for item in data:
        owner = item.get("owner") or {}
        row = [
            item.get("id", ""),
            item.get("name", ""),
            item.get("industry", ""),
            item.get("location", ""),
            item.get("country", ""),
            item.get("email", ""),
            item.get("company_size", ""),
            item.get("org_type", ""),
            item.get("plan", ""),
            item.get("is_active", ""),
            item.get("created_at", ""),
            item.get("updated_at", ""),
            owner.get("id", ""),
            owner.get("name", ""),
            owner.get("email", ""),
            owner.get("is_approved", ""),
            owner.get("is_active", ""),
            owner.get("is_verified", ""),
            owner.get("approved_at", ""),
            owner.get("created_at", ""),
            owner.get("last_login", ""),
            owner.get("last_active", ""),
        ]
        writer.writerow(row)
        yield output.getvalue()
        output.seek(0)
        output.truncate(0)
