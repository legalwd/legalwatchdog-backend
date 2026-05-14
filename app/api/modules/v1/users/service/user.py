import logging
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from sqlalchemy import select

if TYPE_CHECKING:
    from app.api.modules.v1.users.schemas.user_profile_schema import UpdateUserProfileRequest
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.core.custom_exceptions.exceptions import (
    NoFieldsToUpdateError,
    NotFoundError,
    PermissionDeniedError,
    ProcessingError,
)
from app.api.modules.v1.users.models.roles_model import Role
from app.api.modules.v1.users.models.users_model import User

logger = logging.getLogger("app")


class UserCRUD:
    """Service class for User business logic operations."""

    def __init__(self, db: AsyncSession):
        """
        Initialize the UserCRUD with a database session.

        Args:
            db (AsyncSession): The database session for executing queries.
        """
        self.db = db

    async def create_user(
        self,
        email: str,
        name: str,
        hashed_password: str,
        auth_provider: str = "local",
        is_active: bool = True,
        is_verified: bool = False,
        is_approved: bool = False,
    ) -> User:
        """
        Create a new user.

        Args:
            email: User email address
            name: User's full name
            hashed_password: Hashed password
            auth_provider: Authentication provider (default: "local")
            is_active: Whether the user account is active (default: True)
            is_verified: Whether the user's email is verified (default: False)
            is_approved: Whether account is approved by superadmin (default: False)

        Returns:
            User: Created user object

        Raises:
            ProcessingError: If database operation fails
        """
        try:
            user = User(
                email=email,
                name=name,
                hashed_password=hashed_password,
                auth_provider=auth_provider,
                is_active=is_active,
                is_verified=is_verified,
                is_approved=is_approved,
            )

            self.db.add(user)
            await self.db.flush()
            await self.db.refresh(user)

            logger.info(
                "Created user: id=%s, email=%s",
                user.id,
                user.email,
            )

            return user

        except Exception as e:
            await self.db.rollback()
            logger.error("Failed to create user for email=%s: %s", email, str(e), exc_info=True)
            raise ProcessingError(
                message="We're unable to create your account at this time. "
                "Please try again later or contact support if the problem persists."
            )

    @staticmethod
    async def create_google_user(
        db: AsyncSession,
        email: str,
        name: str,
    ) -> User:
        """
        Create a new Google OAuth user.

        Args:
            db: Async database session
            email: User email address
            name: User's full name

        Returns:
            User: Created Google-authenticated user object

        Raises:
            ProcessingError: If database operation fails
        """
        try:
            user = User(
                email=email,
                name=name,
                hashed_password=None,
                auth_provider="google",
                is_active=True,
                is_verified=True,
            )

            db.add(user)
            await db.flush()
            await db.refresh(user)

            logger.info(
                "Created Google OAuth user: id=%s, email=%s",
                user.id,
                user.email,
            )

            return user

        except Exception as e:
            await db.rollback()
            logger.error(
                "Failed to create Google OAuth user for email=%s: %s",
                email,
                str(e),
                exc_info=True,
            )
            raise ProcessingError(
                message="We're unable to complete your Google sign-in at this time. "
                "Please try again later or use email registration."
            )

    @staticmethod
    async def set_user_active_status(db: AsyncSession, user_id: uuid.UUID, is_active: bool) -> User:
        """
        Set a user's active status.

        Args:
            db: Async database session
            user_id: UUID of the user to update
            is_active: The new active status (True for active, False for deactivated)

        Returns:
            User: The updated user object

        Raises:
            NotFoundError: If the user is not found
            ProcessingError: If database operation fails
        """
        try:
            user = await db.get(User, user_id)
            if not user:
                logger.warning(f"User not found for activation status update: user_id={user_id}")
                raise NotFoundError(
                    message="The user account you're trying to update doesn't exist."
                )

            user.is_active = is_active
            user.updated_at = datetime.now(timezone.utc)
            db.add(user)
            await db.commit()
            await db.refresh(user)

            logger.info("User %s active status set to %s", user_id, is_active)
            return user
        except NotFoundError:
            await db.rollback()
            raise
        except Exception as e:
            await db.rollback()
            logger.error(f"Error updating user active status: {str(e)}", exc_info=True)
            raise ProcessingError(message="Failed to update user status. Please try again.")

    @staticmethod
    async def update_user_role(
        db: AsyncSession, user_id: uuid.UUID, new_role_id: uuid.UUID
    ) -> User:
        """
        Update a user's role.

        Args:
            db: Async database session
            user_id: UUID of the user to update
            new_role_id: UUID of the new role to assign

        Returns:
            User: The updated user object

        Raises:
            NotFoundError: If the user or new role is not found
            PermissionDeniedError: If organization mismatch
            ProcessingError: If database operation fails
        """
        try:
            user = await db.get(User, user_id)
            if not user:
                logger.warning(f"User not found for role update: user_id={user_id}")
                raise NotFoundError(
                    message="The user account you're trying to update doesn't exist."
                )

            new_role = await db.get(Role, new_role_id)
            if not new_role:
                logger.warning(f"Role not found for user role update: role_id={new_role_id}")
                raise NotFoundError(message="The role you're trying to assign doesn't exist.")

            if user.organization_id != new_role.organization_id:
                logger.warning(
                    f"Organization mismatch: user_org={user.organization_id}, "
                    f"role_org={new_role.organization_id}, user_id={user_id}, role_id={new_role_id}"
                )
                raise PermissionDeniedError(
                    message="You cannot assign a role from a different organization to this user."
                )

            user.role_id = new_role_id
            user.updated_at = datetime.now(timezone.utc)
            db.add(user)
            await db.commit()
            await db.refresh(user)

            logger.info("User %s role updated to %s", user_id, new_role_id)
            return user
        except (NotFoundError, PermissionDeniedError):
            await db.rollback()
            raise
        except Exception as e:
            await db.rollback()
            logger.error(f"Error updating user role: {str(e)}", exc_info=True)
            raise ProcessingError(message="Failed to update user role. Please try again.")

    @staticmethod
    async def create_admin_user(
        db: AsyncSession,
        email: str,
        name: str,
        hashed_password: str,
        organization_id: uuid.UUID,
        role_id: uuid.UUID,
        auth_provider: str = "local",
    ) -> User:
        """
        Create an admin user for an organization.

        Args:
            db: Async database session
            email: User email address
            name: User's full name
            hashed_password: Hashed password
            organization_id: UUID of the organization
            role_id: UUID of the admin role
            auth_provider: Authentication provider (default: "local")

        Returns:
            User: Created user object

        Raises:
            ProcessingError: If database operation fails
        """
        try:
            user = User(
                email=email,
                name=name,
                hashed_password=hashed_password,
                organization_id=organization_id,
                role_id=role_id,
                auth_provider=auth_provider,
                is_active=True,
                is_verified=True,
            )

            db.add(user)
            await db.flush()
            await db.refresh(user)

            logger.info(
                "Created admin user: id=%s, email=%s, organization_id=%s",
                user.id,
                user.email,
                user.organization_id,
            )

            return user

        except Exception as e:
            await db.rollback()
            logger.error(
                "Failed to create admin user for email=%s: %s",
                email,
                str(e),
                exc_info=True,
            )
            raise ProcessingError(
                message="We're unable to create the admin account at this time. "
                "Please try again later or contact support."
            )

    @staticmethod
    async def get_by_id(db: AsyncSession, user_id: uuid.UUID) -> Optional[User]:
        """
        Get user by ID.

        Args:
            db: Database session
            user_id: User UUID

        Returns:
            User or None if not found
        """
        result = await db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_email(db: AsyncSession, email: str) -> Optional[User]:
        """
        Get user by email.

        Args:
            db: Database session
            email: User email address

        Returns:
            User or None if not found
        """
        result = await db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    @staticmethod
    async def update_user_organization_and_role(
        db: AsyncSession,
        user_id: uuid.UUID,
        organization_id: uuid.UUID,
        role_id: uuid.UUID,
    ) -> User:
        """
        Update user's organization and role.

        This is used when a user creates an organization and becomes its admin.

        Args:
            db: Database session
            user_id: User UUID
            organization_id: Organization UUID
            role_id: Role UUID

        Returns:
            Updated user instance

        Raises:
            NotFoundError: If user not found
            ProcessingError: If database operation fails
        """
        try:
            user = await UserCRUD.get_by_id(db, user_id)
            if not user:
                logger.warning(
                    f"User not found for organization update: user_id={user_id}, "
                    f"org_id={organization_id}, role_id={role_id}"
                )
                raise NotFoundError(
                    message="The user account you're trying to update doesn't exist."
                )

            user.organization_id = organization_id
            user.role_id = role_id
            user.updated_at = datetime.now(timezone.utc)

            db.add(user)
            await db.flush()
            await db.refresh(user)

            logger.info(
                f"Updated user {user_id}: organization_id={organization_id}, role_id={role_id}"
            )

            return user
        except NotFoundError:
            await db.rollback()
            raise
        except Exception as e:
            await db.rollback()
            logger.error(f"Error updating user organization and role: {str(e)}", exc_info=True)
            raise ProcessingError(message="Failed to update user membership. Please try again.")

    @staticmethod
    async def update_user(db: AsyncSession, user_id: uuid.UUID, **kwargs) -> User:
        """
        Update user fields.

        Args:
            db: Database session
            user_id: User UUID
            **kwargs: Fields to update

        Returns:
            Updated user instance

        Raises:
            NotFoundError: If user not found
            ProcessingError: If database operation fails
        """
        try:
            user = await UserCRUD.get_by_id(db, user_id)
            if not user:
                logger.warning(
                    f"User not found for update: user_id={user_id}, fields={list(kwargs.keys())}"
                )
                raise NotFoundError(
                    message="The user account you're trying to update doesn't exist."
                )

            for key, value in kwargs.items():
                if hasattr(user, key) and value is not None:
                    setattr(user, key, value)

            user.updated_at = datetime.now(timezone.utc)
            db.add(user)
            await db.flush()
            await db.refresh(user)

            logger.info(f"Updated user {user_id}: {kwargs}")
            return user
        except NotFoundError:
            await db.rollback()
            raise
        except Exception as e:
            await db.rollback()
            logger.error(f"Error updating user: {str(e)}", exc_info=True)
            raise ProcessingError(message="Failed to update user profile. Please try again.")

    async def get_user_profile(self, user_id: uuid.UUID) -> dict:
        """
        Fetches user, memberships, organizations, and roles
        """

        from app.api.modules.v1.organization.models.organization_model import Organization
        from app.api.modules.v1.organization.models.user_organization_model import UserOrganization
        from app.api.modules.v1.users.models.roles_model import Role

        logger.info(f"Fetching optimized profile for user_id={user_id}")

        try:
            user = await UserCRUD.get_by_id(self.db, user_id)
            if not user:
                logger.warning(f"User profile not found: user_id={user_id}")
                raise NotFoundError(
                    message="Your profile could not be found. Please try logging in again."
                )

            stmt = (
                select(UserOrganization, Organization, Role)
                .join(Organization, Organization.id == UserOrganization.organization_id)
                .join(Role, Role.id == UserOrganization.role_id, isouter=True)
                .where(
                    UserOrganization.user_id == user_id,
                    UserOrganization.is_deleted.is_(False),
                    UserOrganization.is_active,
                    Organization.is_active,
                    Organization.deleted_at.is_(None),
                )
            )

            result = await self.db.execute(stmt)
            rows = result.all()

            organizations = []
            for membership, org, role in rows:
                organizations.append(
                    {
                        "organization_id": str(org.id),
                        "name": org.name,
                        "industry": org.industry,
                        "is_active": org.is_active,
                        "membership_active": membership.is_active,
                        "role": {
                            "id": str(role.id) if role else None,
                            "name": role.name if role else None,
                            "permissions": role.permissions if role else {},
                        },
                        "joined_at": membership.created_at.isoformat(),
                        "membership_updated_at": membership.updated_at.isoformat()
                        if membership.updated_at
                        else None,
                    }
                )

            profile = {
                "user": {
                    "id": str(user.id),
                    "email": user.email,
                    "name": user.name,
                    "auth_provider": user.auth_provider,
                    "profile_picture_url": user.profile_picture_url,
                    "provider_user_id": user.provider_user_id,
                    "provider_profile_data": user.provider_profile_data,
                    "is_active": user.is_active,
                    "is_verified": user.is_verified,
                    "is_superadmin": user.is_superadmin,
                    "created_at": user.created_at.isoformat(),
                    "updated_at": user.updated_at.isoformat(),
                },
                "organizations": organizations,
                "statistics": {
                    "total_organizations": len(organizations),
                    "active_memberships": sum(
                        1 for org in organizations if org["membership_active"]
                    ),
                    "admin_roles": sum(
                        1
                        for org in organizations
                        if org["role"]["name"] == "Admin"
                        or org["role"]["permissions"].get("manage_organization", False)
                    ),
                },
            }

            logger.info(f"Successfully retrieved profile (optimized) for user_id={user_id}")
            return profile
        except NotFoundError:
            raise
        except Exception as e:
            logger.error(
                f"Error fetching optimized profile for user_id={user_id}: {str(e)}",
                exc_info=True,
            )
            raise ProcessingError(
                message="We're unable to load your profile at this time. "
                "Please refresh the page or try again later."
            )

    async def update_user_profile(
        self, user_id: uuid.UUID, payload: "UpdateUserProfileRequest"
    ) -> dict:
        """
        Update user profile information. Moves business logic from the route.
        """
        try:
            update_data = {}
            if payload.name is not None:
                update_data["name"] = payload.name
            if payload.avatar_url is not None:
                update_data["avatar_url"] = payload.avatar_url

            if not update_data:
                logger.warning(f"No update data provided for user_id={user_id}")
                raise NoFieldsToUpdateError(message="No fields to update")

            updated_user = await self.update_user(db=self.db, user_id=user_id, **update_data)
            await self.db.commit()

            return {
                "id": str(updated_user.id),
                "email": updated_user.email,
                "name": updated_user.name,
                "avatar_url": updated_user.avatar_url,
                "is_active": updated_user.is_active,
                "is_verified": updated_user.is_verified,
                "created_at": updated_user.created_at.isoformat(),
                "updated_at": updated_user.updated_at.isoformat(),
            }
        except (NotFoundError, NoFieldsToUpdateError):
            await self.db.rollback()
            raise
        except Exception as e:
            await self.db.rollback()
            logger.exception(f"Error updating user profile for user_id={user_id}: {str(e)}")
            raise ProcessingError(message="Failed to update user profile. Please try again.")

    async def upload_profile_picture(
        self,
        user_id: uuid.UUID,
        file_content: bytes,
        filename: str,
        content_type: str,
    ) -> dict:
        """
        Handle profile picture upload and database update.

        Validates file type and size, uploads to MinIO, and updates user's profile_picture_url.
        """
        import os

        from app.api.core.config import settings
        from app.api.core.custom_exceptions.exceptions import (
            FileTooLargeError,
            InvalidFileTypeError,
        )
        from app.api.modules.v1.scraping.storage.minio_storage import upload_profile_picture

        # Validate file type
        allowed_types = ["image/jpeg", "image/png", "image/gif", "image/webp"]
        if content_type not in allowed_types:
            logger.warning(f"Invalid file type for profile picture: {content_type}")
            raise InvalidFileTypeError(
                message="Invalid file type. Only JPEG, PNG, GIF, and WebP images are allowed."
            )

        # Validate file size (5MB max)
        max_size = 5 * 1024 * 1024
        if len(file_content) > max_size:
            logger.warning(f"File too large for profile picture: {len(file_content)} bytes")
            raise FileTooLargeError(message="File too large. Maximum size is 5MB.")

        try:
            file_extension = os.path.splitext(filename)[1].lower()
            unique_filename = f"profile-pictures/{user_id}/{uuid.uuid4()}{file_extension}"

            bucket_name = settings.MINIO_PROFILE_BUCKET
            upload_profile_picture(
                file_data=file_content,
                bucket_name=bucket_name,
                object_name=unique_filename,
                content_type=content_type,
            )

            minio_public_url = getattr(settings, "MINIO_PUBLIC_URL", None)
            if minio_public_url:
                base_url = minio_public_url.rstrip("/")
                picture_url = f"{base_url}/{bucket_name}/{unique_filename}"
            else:
                protocol = "https" if settings.MINIO_SECURE else "http"
                picture_url = (
                    f"{protocol}://{settings.MINIO_ENDPOINT}/{bucket_name}/{unique_filename}"
                )

            await self.update_user(db=self.db, user_id=user_id, profile_picture_url=picture_url)
            await self.db.commit()

            logger.info(f"Successfully uploaded profile picture for user_id={user_id}")
            return {"profile_picture_url": picture_url}

        except (InvalidFileTypeError, FileTooLargeError):
            raise
        except Exception as e:
            await self.db.rollback()
            logger.exception(f"Error uploading profile picture for user_id={user_id}: {str(e)}")
            raise ProcessingError(message="Failed to upload profile picture. Please try again.")

    async def get_my_invitations(self, email: str, page: int, limit: int) -> dict:
        """
        Get pending invitations for user email.
        """
        from app.api.modules.v1.organization.schemas.invitation_schema import InvitationResponse
        from app.api.modules.v1.organization.service.invitation_service import InvitationCRUD
        from app.api.utils.pagination import calculate_pagination

        try:
            invitations, total = await InvitationCRUD.get_pending_invitations_for_user_email(
                self.db, email, page, limit
            )

            pagination = calculate_pagination(total, page, limit)
            invitation_responses = [
                InvitationResponse.model_validate(inv).model_dump() for inv in invitations
            ]

            return {
                "items": invitation_responses,
                "pagination": pagination,
            }
        except Exception as e:
            logger.exception(f"Error retrieving invitations for email={email}: {str(e)}")
            raise ProcessingError(message="Failed to retrieve invitations. Please try again.")

    async def get_all_user_organizations(self, user_id: uuid.UUID, page: int, limit: int) -> dict:
        """
        Get all organizations a user is a member of.
        """
        from app.api.modules.v1.organization.service.organization_service import OrganizationService

        try:
            service = OrganizationService(self.db)
            return await service.get_user_organizations(
                user_id=user_id,
                page=page,
                limit=limit,
            )
        except Exception as e:
            logger.exception(f"Error retrieving organizations for user_id={user_id}: {str(e)}")
            raise ProcessingError(message="Failed to retrieve organizations. Please try again.")

    async def get_user_organization_details(
        self,
        user_id: uuid.UUID,
        organization_id: uuid.UUID,
        current_user_id: uuid.UUID,
    ) -> dict:
        """
        Get details of a specific organization for a user.
        """
        if user_id != current_user_id:
            logger.warning(
                f"Unauthorized attempt to view other user's organization: "
                f"requester={current_user_id}, target={user_id}"
            )
            raise PermissionDeniedError(message="You can only view your own organization details")

        from app.api.modules.v1.organization.service.organization_service import OrganizationService

        try:
            service = OrganizationService(self.db)
            return await service.get_organization_details(
                organization_id=organization_id,
                requesting_user_id=user_id,
            )
        except (NotFoundError, PermissionDeniedError):
            raise
        except Exception as e:
            logger.exception(
                f"Error retrieving organization details for org_id={organization_id}: {str(e)}"
            )
            raise ProcessingError(
                message="Failed to retrieve organization details. Please try again."
            )

    async def get_organization_details(
        self, organization_id: uuid.UUID, requesting_user_id: uuid.UUID
    ) -> dict:
        """
        Get organization details.
        """
        from app.api.modules.v1.organization.service.organization_service import OrganizationService

        try:
            service = OrganizationService(self.db)
            return await service.get_organization_details(
                organization_id=organization_id,
                requesting_user_id=requesting_user_id,
            )
        except (NotFoundError, PermissionDeniedError):
            raise
        except Exception as e:
            logger.exception(
                f"Error retrieving organization details for org_id={organization_id}: {str(e)}"
            )
            raise ProcessingError(
                message="Failed to retrieve organization details. Please try again."
            )
