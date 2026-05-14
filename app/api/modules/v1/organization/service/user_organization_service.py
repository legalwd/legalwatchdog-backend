import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func
from sqlalchemy import select as sa_select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.api.modules.v1.organization.models.organization_model import Organization
from app.api.modules.v1.organization.models.user_organization_model import UserOrganization
from app.api.modules.v1.users.models.roles_model import Role
from app.api.modules.v1.users.models.users_model import User

logger = logging.getLogger("app")


class UserOrganizationCRUD:
    """CRUD operations for UserOrganization model."""

    @staticmethod
    async def add_user_to_organization(
        db: AsyncSession,
        user_id: uuid.UUID,
        organization_id: uuid.UUID,
        role_id: uuid.UUID,
        is_active: bool = True,
        title: Optional[str] = None,
    ) -> UserOrganization:
        """
        Add a user to an organization with a specific role.

        Args:
            db: Async database session
            user_id: UUID of the user
            organization_id: UUID of the organization
            role_id: UUID of the role in that organization
            is_active: Whether the membership is active
            title: Optional job title in the organization

        Returns:
            UserOrganization: Created membership object

        Raises:
            ValueError: If membership already exists
            Exception: If database operation fails
        """
        try:
            existing = await UserOrganizationCRUD.get_user_organization(
                db, user_id, organization_id
            )
            if existing:
                logger.warning(
                    f"User already member of organization: "
                    f"user_id={user_id}, org_id={organization_id}"
                )
                raise ValueError("This user is already a member of the organization.")

            membership = UserOrganization(
                user_id=user_id,
                organization_id=organization_id,
                role_id=role_id,
                is_active=is_active,
                title=title,
            )

            db.add(membership)
            await db.flush()
            await db.refresh(membership)

            logger.info(
                "Added user %s to organization %s with role %s",
                user_id,
                organization_id,
                role_id,
            )

            return membership

        except ValueError:
            raise
        except Exception as e:
            logger.error(
                "Failed to add user %s to organization %s: %s",
                user_id,
                organization_id,
                str(e),
                exc_info=True,
            )
            raise Exception("Failed to add user to organization")

    @staticmethod
    async def get_user_organization(
        db: AsyncSession,
        user_id: uuid.UUID,
        organization_id: uuid.UUID,
    ) -> Optional[UserOrganization]:
        """
        Get a specific user-organization membership.

        This method only returns non-deleted memberships. Soft-deleted
        memberships (is_deleted=True) are treated as non-existent for
        membership checks (e.g. invitations, access control).

        Args:
            db: Database session
            user_id: User UUID
            organization_id: Organization UUID

        Returns:
            UserOrganization or None if not found
        """
        result = await db.execute(
            select(UserOrganization).where(
                UserOrganization.user_id == user_id,
                UserOrganization.organization_id == organization_id,
                UserOrganization.is_deleted.is_(False),
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_user_organizations(
        db: AsyncSession,
        user_id: uuid.UUID,
        active_only: bool = True,
    ) -> list[UserOrganization]:
        """
        Get all organizations a user belongs to.

        Args:
            db: Database session
            user_id: User UUID
            active_only: Only return active memberships

        Returns:
            List of UserOrganization objects
        """
        query = select(UserOrganization).where(UserOrganization.user_id == user_id)

        if active_only:
            query = query.where(UserOrganization.is_active)

        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def get_all_user_organizations(
        db: AsyncSession,
        user_id: uuid.UUID,
        skip: int = 0,
        limit: int = 10,
        active_only: bool = True,
    ) -> dict:
        """
        Get paginated organizations a user belongs to with database-level pagination.

        Args:
            db: Database session
            user_id: User UUID
            skip: Number of records to skip
            limit: Maximum number of records to return
            active_only: Only return active memberships

        Returns:
            Dictionary with organizations list and total count
        """
        membership_query = select(UserOrganization).where(UserOrganization.user_id == user_id)

        if active_only:
            membership_query = membership_query.where(UserOrganization.is_active)

        count_query = (
            sa_select(func.count())
            .select_from(UserOrganization)
            .where(UserOrganization.user_id == user_id)
        )
        if active_only:
            count_query = count_query.where(UserOrganization.is_active)

        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        membership_query = membership_query.offset(skip).limit(limit)
        memberships_result = await db.execute(membership_query)
        memberships = list(memberships_result.scalars().all())

        organizations = []
        for membership in memberships:
            org_result = await db.execute(
                select(Organization).where(
                    Organization.id == membership.organization_id, Organization.deleted_at.is_(None)
                )
            )
            org = org_result.scalar_one_or_none()

            if not org:
                logger.warning(
                    f"Organization {membership.organization_id} not found for user {user_id}"
                )
                continue

            role = await db.get(Role, membership.role_id)

            organizations.append(
                {
                    "organization_id": str(org.id),
                    "name": org.name,
                    "industry": org.industry,
                    "is_active": org.is_active,
                    "user_role": role.name if role else None,
                    "created_at": org.created_at.isoformat(),
                    "updated_at": org.updated_at.isoformat() if org.updated_at else None,
                }
            )

        return {"organizations": organizations, "total": total}

    @staticmethod
    async def get_all_users_in_organization(
        db: AsyncSession,
        organization_id: uuid.UUID,
        skip: int = 0,
        limit: int = 10,
        active_only: Optional[bool] = None,
        membership_active: Optional[bool] = None,
        role_names: Optional[list[str]] = None,
    ) -> dict:
        """
        Get paginated users in an organization with their details (optimized, no N+1 queries).
        """

        role_ids = None

        if role_names:
            normalized = [name.lower() for name in role_names]

            result = await db.execute(
                select(Role).where(
                    Role.organization_id == organization_id,
                    func.lower(Role.name).in_(normalized),
                )
            )
            roles = result.scalars().all()

            if not roles:
                logger.warning(f"No roles found matching {role_names} in org {organization_id}")
                return {"users": [], "total": 0}

            role_ids = [role.id for role in roles]

            found = {role.name.lower() for role in roles}
            missing = set(normalized) - found
            if missing:
                logger.warning(f"Roles not found in org {organization_id}: {missing}")

        count_query = sa_select(func.count())
        count_query = count_query.select_from(UserOrganization).join(
            User, User.id == UserOrganization.user_id
        )
        count_query = count_query.where(
            UserOrganization.organization_id == organization_id,
            UserOrganization.is_deleted.is_(False),
        )

        if membership_active is not None:
            count_query = count_query.where(UserOrganization.is_active == membership_active)

        if role_ids:
            count_query = count_query.where(UserOrganization.role_id.in_(role_ids))

        if active_only is not None:
            count_query = count_query.where(User.is_active == active_only)

        total = (await db.execute(count_query)).scalar() or 0

        query = (
            select(
                UserOrganization,
                User,
                Role,
            )
            .join(User, User.id == UserOrganization.user_id)
            .join(Role, Role.id == UserOrganization.role_id)
            .where(
                UserOrganization.organization_id == organization_id,
                UserOrganization.is_deleted.is_(False),
            )
        )

        if membership_active is not None:
            query = query.where(UserOrganization.is_active == membership_active)

        if role_ids:
            query = query.where(UserOrganization.role_id.in_(role_ids))

        if active_only is not None:
            query = query.where(User.is_active == active_only)

        query = query.offset(skip).limit(limit)

        result = await db.execute(query)
        rows = result.all()

        users = []
        for membership, user, role in rows:
            users.append(
                {
                    "user_id": str(user.id),
                    "email": user.email,
                    "name": user.name,
                    "avatar_url": user.avatar_url,
                    "is_active": user.is_active,
                    "is_verified": user.is_verified,
                    "role": role.name,
                    "role_id": str(role.id),
                    "title": membership.title,
                    "department": membership.department,
                    "membership_active": membership.is_active,
                    "joined_at": membership.joined_at.isoformat(),
                    "created_at": user.created_at.isoformat(),
                }
            )

        return {"users": users, "total": total}

    @staticmethod
    async def update_user_role_in_organization(
        db: AsyncSession,
        user_id: uuid.UUID,
        organization_id: uuid.UUID,
        new_role_id: uuid.UUID,
    ) -> UserOrganization:
        """
        Update a user's role in an organization.

        Args:
            db: Database session
            user_id: User UUID
            organization_id: Organization UUID
            new_role_id: New role UUID

        Returns:
            Updated UserOrganization object

        Raises:
            ValueError: If membership not found
        """
        membership = await UserOrganizationCRUD.get_user_organization(db, user_id, organization_id)
        if not membership:
            logger.warning(
                f"Membership not found for role update: user_id={user_id}, org_id={organization_id}"
            )
            raise ValueError(
                "The user membership in this organization could not be found. "
                "Please verify the user is a member."
            )

        membership.role_id = new_role_id
        membership.updated_at = datetime.now(timezone.utc)

        db.add(membership)
        await db.flush()
        await db.refresh(membership)

        logger.info(
            "Updated user %s role to %s in organization %s",
            user_id,
            new_role_id,
            organization_id,
        )

        return membership

    @staticmethod
    async def set_membership_status(
        db: AsyncSession,
        user_id: uuid.UUID,
        organization_id: uuid.UUID,
        is_active: bool,
    ) -> UserOrganization:
        """
        Activate or deactivate a user's membership in an organization.

        Args:
            db: Database session
            user_id: User UUID
            organization_id: Organization UUID
            is_active: New active status

        Returns:
            Updated UserOrganization object

        Raises:
            ValueError: If membership not found
        """
        membership = await UserOrganizationCRUD.get_user_organization(db, user_id, organization_id)
        if not membership:
            logger.warning(
                f"Membership not found for status update: "
                f"user_id={user_id}, org_id={organization_id}"
            )
            raise ValueError(
                "The user membership in this organization could not be found. "
                "Please verify the user is a member."
            )

        membership.is_active = is_active
        membership.updated_at = datetime.now(timezone.utc)

        db.add(membership)
        await db.flush()
        await db.refresh(membership)

        logger.info(
            "Set user %s membership status to %s in organization %s",
            user_id,
            is_active,
            organization_id,
        )

        return membership

    @staticmethod
    async def update_member_details(
        db: AsyncSession,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        user_updates: dict,
        membership_updates: dict,
    ) -> tuple[User, UserOrganization]:
        """
        Update member details including user and membership info.

        Args:
            db: Database session
            organization_id: Organization UUID
            user_id: User UUID to update
            user_updates: Dictionary of User fields to update
            membership_updates: Dictionary of UserOrganization fields to update

        Returns:
            Tuple of (updated_user, updated_membership)

        Raises:
            ValueError: If user or membership not found
            Exception: If database operation fails
        """
        try:
            user_result = await db.execute(select(User).where(User.id == user_id))
            user = user_result.scalar_one_or_none()

            if not user:
                logger.warning(f"User not found for member update: user_id={user_id}")
                raise ValueError("The user you're trying to update could not be found.")

            membership = await UserOrganizationCRUD.get_user_organization(
                db, user_id, organization_id
            )

            if not membership:
                logger.warning(
                    f"User not member of organization: user_id={user_id}, org_id={organization_id}"
                )
                raise ValueError("This user is not a member of the organization.")

            if user_updates:
                for key, value in user_updates.items():
                    setattr(user, key, value)
                user.updated_at = datetime.now(timezone.utc)
                db.add(user)

            if membership_updates:
                for key, value in membership_updates.items():
                    setattr(membership, key, value)
                membership.updated_at = datetime.now(timezone.utc)
                db.add(membership)

            await db.flush()
            await db.refresh(user)
            await db.refresh(membership)

            logger.info(f"Updated member user_id={user_id} in org_id={organization_id}")

            return user, membership

        except ValueError:
            raise
        except Exception as e:
            logger.error(
                f"Failed to update member user_id={user_id} in org_id={organization_id}: {str(e)}",
                exc_info=True,
            )
            raise Exception("Failed to update member details")

    @staticmethod
    async def soft_delete_member(
        db: AsyncSession,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        """
        Soft delete a user's membership in an organization.

        Args:
            db: Database session
            organization_id: Organization UUID
            user_id: User UUID to soft delete

        Raises:
            ValueError: If membership not found or already deleted
        """
        try:
            membership = await UserOrganizationCRUD.get_user_organization(
                db, user_id, organization_id
            )

            if not membership:
                logger.warning(
                    f"Cannot delete non-existent membership: "
                    f"user_id={user_id}, org_id={organization_id}"
                )
                raise ValueError("This user is not a member of the organization.")

            if membership.is_deleted:
                logger.warning(
                    f"Membership already deleted: user_id={user_id}, org_id={organization_id}"
                )
                raise ValueError("This membership has already been deleted.")

            membership.is_deleted = True
            membership.deleted_at = datetime.now(timezone.utc)
            db.add(membership)
            await db.flush()

            logger.info(f"Soft deleted member user_id={user_id} from org_id={organization_id}")

        except ValueError:
            raise
        except Exception as e:
            logger.error(
                f"Failed to delete member {user_id} from org {organization_id}: {str(e)}",
                exc_info=True,
            )
            raise ValueError(
                "We're unable to remove the member at this time. "
                "Please try again later or contact support."
            )
