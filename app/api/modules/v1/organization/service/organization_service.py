import logging
import uuid
from typing import Optional

from fastapi import BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import func, select

from app.api.core.dependencies.send_mail import send_email
from app.api.modules.v1.billing.models.billing_account import BillingAccount
from app.api.modules.v1.billing.service.billing_service import get_billing_service
from app.api.modules.v1.organization.models.invitation_model import Invitation
from app.api.modules.v1.organization.models.organization_model import CompanySize, Organization
from app.api.modules.v1.organization.models.user_organization_model import UserOrganization
from app.api.modules.v1.organization.service.invitation_service import InvitationCRUD
from app.api.modules.v1.organization.service.organization_repository import OrganizationCRUD
from app.api.modules.v1.organization.service.user_organization_service import UserOrganizationCRUD
from app.api.modules.v1.projects.models.project_model import Project
from app.api.modules.v1.users.models.roles_model import Role
from app.api.modules.v1.users.service.role import RoleCRUD
from app.api.modules.v1.users.service.user import UserCRUD
from app.api.utils.frontend_client import add_client_query, resolve_frontend_url
from app.api.utils.organization_validations import check_user_permission
from app.api.utils.pagination import calculate_pagination

logger = logging.getLogger("app")


class OrganizationService:
    """Service class for organization business logic."""

    def __init__(self, db: AsyncSession):
        """
        Initialize organization service.

        Args:
            db: Async database session
        """
        self.db = db

    async def create_organization(
        self,
        user_id: uuid.UUID,
        name: str,
        industry: str | None = None,
        country: str | None = None,
        email: str | None = None,
        company_size: CompanySize | None = None,
        org_type: str | None = None,
        job_title: str | None = None,
    ) -> dict:
        """
        Create a new organization and set the user as admin.


        - Validates that the user exists and is verified
        - Creates the organization
        - Creates default roles for the organization (Admin, Member, etc.)
        - Adds the user as admin

        Args:
            user_id: UUID of the user creating the organization
            name: Organization name
            industry: Optional industry type

        Returns:
            dict: Dictionary containing organization and user details

        Raises:
            ValueError: If validation fails
            Exception: For unexpected errors
        """
        cached_user_id = user_id

        logger.info(f"Starting organization creation for user_id={user_id}")

        try:
            user = await UserCRUD.get_by_id(self.db, user_id)
            if not user:
                logger.warning(f"User not found for organization creation: user_id={user_id}")
                raise ValueError("Your account could not be found. Please try logging in again.")

            if not user.is_verified:
                logger.warning(
                    f"Unverified user attempting to create organization: user_id={user_id}"
                )
                raise ValueError(
                    "You must verify your email address before creating an organization. "
                    "Please check your email for the verification link."
                )

            existing_org = await OrganizationCRUD.get_user_org_by_name(
                db=self.db, user_id=user_id, name=name
            )
            if existing_org:
                logger.warning(
                    f"Duplicate organization name: user_id={user_id}, name={name}, "
                    f"existing_org_id={existing_org.id}"
                )
                raise ValueError(
                    "You already have an organization with this name. "
                    "Please choose a different name."
                )

            organization = await OrganizationCRUD.create_organization(
                db=self.db,
                name=name,
                industry=industry,
                country=country,
                email=email,
                company_size=company_size,
                org_type=org_type,
            )

            owner_role = await RoleCRUD.create_owner_role(
                db=self.db,
                organization_id=organization.id,
                role_name="Owner",
                description="Organization owner with full permissions",
            )

            await RoleCRUD.create_admin_role(
                db=self.db,
                organization_id=organization.id,
                role_name="Admin",
                description="Organization administrator with full permissions",
            )

            await RoleCRUD.get_default_user_role(
                db=self.db,
                organization_id=organization.id,
                role_name="Member",
                description="Organization member with basic permissions",
            )

            await RoleCRUD.create_manager_role(
                db=self.db,
                organization_id=organization.id,
                role_name="Manager",
                description="Team manager with elevated project management permissions",
            )
            await UserOrganizationCRUD.add_user_to_organization(
                db=self.db,
                user_id=user_id,
                organization_id=organization.id,
                role_id=owner_role.id,
                is_active=True,
                title=job_title,
            )

            billing_service = get_billing_service(self.db)

            billing_account: BillingAccount = await billing_service.create_billing_account(
                organization_id=organization.id,
                metadata={"created_by": str(user_id)},
            )

            await billing_service._sync_org_billing_from_account(
                db=self.db,
                organization_id=organization.id,
                account=billing_account,
                plan_info=None,
            )

            await self.db.commit()

            logger.info(
                f"Successfully created organization id={organization.id} "
                f"for user_id={user_id} with owner role"
            )

            return {
                "organization_id": str(organization.id),
                "organization_name": organization.name,
                "user_id": str(user_id),
                "role": owner_role.name,
                "billing_account_id": str(billing_account.id),
                "billing_status": billing_account.status.value
                if hasattr(billing_account.status, "value")
                else billing_account.status,
            }

        except ValueError as e:
            logger.warning(
                f"Validation error in organization creation for user_id={cached_user_id}: {str(e)}"
            )
            await self.db.rollback()
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error in organization creation for user_id={cached_user_id}: {str(e)}",
                exc_info=True,
            )
            await self.db.rollback()
            raise Exception("An error occurred while creating the organization. Please try again.")

    async def get_user_role_in_organization(
        self,
        user_id: uuid.UUID,
        organization_id: uuid.UUID,
    ) -> str | None:
        """
        Get the user's role in a specific organization.

        Args:
            user_id: User UUID
            organization_id: Organization UUID

        Returns:
            Role name or None if user is not a member
        """
        membership = await UserOrganizationCRUD.get_user_organization(
            self.db, user_id, organization_id
        )

        if not membership or not membership.is_active:
            return None

        role = await self.db.get(Role, membership.role_id)
        return role.name if role else None

    async def get_organization_details(
        self,
        organization_id: uuid.UUID,
        requesting_user_id: uuid.UUID,
    ) -> dict:
        """
        Get organization details.

        Args:
            organization_id: Organization UUID
            requesting_user_id: UUID of the user requesting the details

        Returns:
            dict: Dictionary containing organization details

        Raises:
            ValueError: If validation fails
            Exception: For unexpected errors
        """
        logger.info(
            f"Fetching organization details for org_id={organization_id} "
            f"by user_id={requesting_user_id}"
        )

        try:
            organization = await OrganizationCRUD.get_by_id(self.db, organization_id)
            if not organization:
                logger.warning(
                    f"Organization not found for details: org_id={organization_id}, "
                    f"user_id={requesting_user_id}"
                )
                raise ValueError("The organization you're trying to access doesn't exist.")

            membership = await UserOrganizationCRUD.get_user_organization(
                self.db, requesting_user_id, organization_id
            )

            if not membership or not membership.is_active:
                logger.warning(
                    f"User lacks organization access: user_id={requesting_user_id}, "
                    f"org_id={organization_id}, has_membership={membership is not None}"
                )
                raise ValueError(
                    "You don't have access to this organization. "
                    "Please contact your administrator for access."
                )

            projects_count_query = (
                select(func.count())
                .select_from(Project)
                .where(Project.org_id == organization_id, ~Project.is_deleted)
            )
            projects_count_result = await self.db.execute(projects_count_query)
            projects_count = projects_count_result.scalar() or 0

            logger.info(f"Successfully retrieved organization details for org_id={organization_id}")

            return {
                "id": str(organization.id),
                "name": organization.name,
                "industry": organization.industry,
                "location": organization.location,
                "country": organization.country,
                "email": organization.email,
                "company_size": organization.company_size,
                "org_type": organization.org_type,
                "plan": organization.plan,
                "logo_url": organization.logo_url,
                "settings": organization.settings,
                "billing_info": organization.billing_info,
                "is_active": organization.is_active,
                "projects_count": projects_count,
                "created_at": organization.created_at.isoformat(),
                "updated_at": organization.updated_at.isoformat(),
            }

        except ValueError as e:
            logger.warning(
                f"Validation error fetching organization org_id={organization_id}: {str(e)}"
            )
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error fetching organization org_id={organization_id}: {str(e)}",
                exc_info=True,
            )
            raise Exception("Failed to retrieve organization details")

    async def update_organization(
        self,
        organization_id: uuid.UUID,
        requesting_user_id: uuid.UUID,
        name: str | None = None,
        industry: str | None = None,
        country: str | None = None,
        email: str | None = None,
        company_size: CompanySize | None = None,
        org_type: str | None = None,
        is_active: bool | None = None,
    ) -> dict:
        """
        Update organization details.

        Args:
            organization_id: Organization UUID
            requesting_user_id: UUID of the user requesting the update
            name: Optional new organization name
            industry: Optional new industry
            is_active: Optional new active status

        Returns:
            dict: Dictionary containing updated organization details

        Raises:
            ValueError: If validation fails
            Exception: For unexpected errors
        """
        logger.info(
            f"Updating organization org_id={organization_id} by user_id={requesting_user_id}"
        )

        try:
            organization = await OrganizationCRUD.get_by_id(self.db, organization_id)
            if not organization:
                logger.warning(
                    f"Organization not found for update: org_id={organization_id}, "
                    f"user_id={requesting_user_id}"
                )
                raise ValueError("The organization you're trying to update doesn't exist.")

            has_permission = await check_user_permission(
                self.db, requesting_user_id, organization_id, "manage_organization"
            )

            if not has_permission:
                logger.warning(
                    f"User lacks permission to update organization: user_id={requesting_user_id}, "
                    f"org_id={organization_id}"
                )
                raise ValueError(
                    "You don't have permission to update this organization. "
                    "Please contact your organization owner."
                )

            if name and name != organization.name:
                existing_org = await OrganizationCRUD.get_user_org_by_name(
                    db=self.db, user_id=requesting_user_id, name=name
                )
                if existing_org and existing_org.id != organization_id:
                    logger.warning(
                        f"Duplicate organization name on update: user_id={requesting_user_id}, "
                        f"name={name}"
                    )
                    raise ValueError(
                        "You already have an organization with this name. "
                        "Please choose a different name."
                    )

            updated_organization: Organization = await OrganizationCRUD.update(
                db=self.db,
                organization_id=organization_id,
                name=name,
                industry=industry,
                country=country,
                email=email,
                company_size=company_size,
                org_type=org_type,
                is_active=is_active,
            )

            await self.db.commit()

            membership: UserOrganization | None = await UserOrganizationCRUD.get_user_organization(
                self.db, requesting_user_id, organization_id
            )
            role = await self.db.get(Role, membership.role_id) if membership else None

            logger.info(f"Successfully updated organization org_id={organization_id}")

            return {
                "organization_id": str(updated_organization.id),
                "name": updated_organization.name,
                "industry": updated_organization.industry,
                "country": updated_organization.country,
                "email": updated_organization.email,
                "company_size": updated_organization.company_size,
                "org_type": updated_organization.org_type,
                "settings": updated_organization.settings,
                "plan": updated_organization.plan,
                "billing_info": updated_organization.billing_info,
                "is_active": updated_organization.is_active,
                "created_at": updated_organization.created_at.isoformat(),
                "updated_at": updated_organization.updated_at.isoformat(),
                "user_role": role.name if role else None,
            }

        except ValueError as e:
            logger.warning(
                f"Validation error updating organization org_id={organization_id}: {str(e)}"
            )
            await self.db.rollback()
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error updating organization org_id={organization_id}: {str(e)}",
                exc_info=True,
            )
            await self.db.rollback()
            raise Exception("Failed to update organization")

    async def send_invitation(
        self,
        background_tasks: BackgroundTasks,
        organization_id: uuid.UUID,
        invited_email: str,
        inviter_id: uuid.UUID,
        role_name: Optional[str] = "Member",
        client: str | None = None,
    ) -> Invitation:
        """
        Send an invitation to a user to join an organization.

        - Generates a unique token.
        - Creates an invitation record in the database.
        - Sends an email to the invited user with the invitation link.

        Args:
            organization_id: UUID of the organization the user is invited to
            invited_email: Email address of the user to invite
            inviter_id: UUID of the user sending the invitation (admin)
            role_name: Role name to assign the invited user (default: "Member")

        Returns:
            Invitation: The created invitation object

        Raises:
            ValueError: If the organization or inviter is not found,
            or if the user is already a member
            Exception: For unexpected errors during the invitation process
        """
        logger.info(
            f"Send invite org_id={organization_id} to email={invited_email} by inviter={inviter_id}"
        )

        try:
            has_permission = await check_user_permission(
                self.db, inviter_id, organization_id, "invite_users"
            )
            if not has_permission:
                raise ValueError("You do not have permission to invite users to this organization")

            organization = await OrganizationCRUD.get_by_id(self.db, organization_id)
            if not organization:
                raise ValueError("Organization not found")

            if organization.deleted_at:
                raise ValueError("Cannot send invitations for a deleted organization")

            organization_name = organization.name

            inviter = await UserCRUD.get_by_id(self.db, inviter_id)
            if not inviter:
                raise ValueError("Inviter user not found")

            existing_user = await UserCRUD.get_by_email(self.db, invited_email)
            if existing_user:
                existing_membership = await UserOrganizationCRUD.get_user_organization(
                    self.db, user_id=existing_user.id, organization_id=organization_id
                )
                if existing_membership:
                    raise ValueError("User is already a member of this organization")

            existing_invitation = await InvitationCRUD.get_pending_invitation_for_email_and_org(
                self.db, invited_email, organization_id
            )
            if existing_invitation:
                raise ValueError(
                    "A pending invitation already exists for this email address. "
                    "Please cancel the existing invitation first or wait for it to expire."
                )

            role = await RoleCRUD.get_role_by_name_and_organization(
                self.db, role_name, organization_id
            )
            if not role:
                logger.warning(
                    f"Role not found in organization: role_name={role_name}, "
                    f"org_id={organization_id}"
                )
                raise ValueError(
                    "The role you specified doesn't exist in this organization. "
                    "Please contact your administrator."
                )

            role_id = role.id

            token = str(uuid.uuid4())

            invitation = await InvitationCRUD.create_invitation(
                db=self.db,
                organization_id=organization_id,
                organization_name=organization_name,
                invited_email=invited_email,
                inviter_id=inviter_id,
                token=token,
                role_id=role_id,
                role_name=role_name,
            )

            logger.info(
                "INVITATION TOKEN GENERATED - Token: %s, Email: %s, Org: %s",
                token,
                invited_email,
                organization_id,
            )

            frontend_url = resolve_frontend_url(client)
            invitation_link = add_client_query(
                f"{frontend_url}/auth/accept-invite/{token}",
                client,
            )

            logger.info("TESTING - Invitation link: %s", invitation_link)

            context = {
                "organization_name": organization.name,
                "inviter_name": inviter.name,
                "invited_email": invited_email,
                "invitation_link": invitation_link,
            }

            background_tasks.add_task(
                send_email,
                template_name="invitation_email.html",
                subject=f"You're invited to join {organization.name} as {role_name}!",
                recipient=invited_email,
                context=context,
            )
            logger.info(f"Invitation email queued for background sending to {invited_email}")
            await self.db.commit()
            return invitation

        except ValueError:
            await self.db.rollback()
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error sending invitation for org_id={organization_id}: {str(e)}",
                exc_info=True,
            )
            await self.db.rollback()
            raise Exception("An error occurred while sending the invitation. Please try again.")

    async def get_admin_organization(
        self,
        user_id: uuid.UUID,
    ) -> list[dict]:
        """
        Return all organizations where the user is an Admin.
        """
        memberships = await UserOrganizationCRUD.get_user_organizations(
            self.db, user_id, active_only=True
        )

        admin_orgs = []
        for membership in memberships:
            role = await self.db.get(Role, membership.role_id)
            if not role:
                continue

            if role.name == "Admin" or role.permissions.get("manage_organization", False):
                org = await OrganizationCRUD.get_by_id(self.db, membership.organization_id)
                if org:
                    admin_orgs.append(
                        {
                            "organization_id": str(org.id),
                            "name": org.name,
                            "industry": org.industry,
                            "is_active": org.is_active,
                            "created_at": org.created_at.isoformat(),
                            "updated_at": org.updated_at.isoformat(),
                            "user_role": role.name,
                        }
                    )

        return admin_orgs

    async def get_user_organizations(
        self,
        user_id: uuid.UUID,
        page: int = 1,
        limit: int = 10,
    ) -> dict:
        """
        Get all organizations where the user is a member (paginated).

        Args:
            user_id: User UUID
            page: Page number (default: 1)
            limit: Items per page (default: 10)

        Returns:
            dict: Dictionary with paginated organizations and metadata
        """
        skip = (page - 1) * limit

        result = await UserOrganizationCRUD.get_all_user_organizations(
            db=self.db,
            user_id=user_id,
            skip=skip,
            limit=limit,
        )

        organizations = result["organizations"]
        total = result["total"]

        pagination = calculate_pagination(total=total, page=page, limit=limit)

        return {"organizations": organizations, **pagination}

    async def get_organization_users(
        self,
        organization_id: uuid.UUID,
        requesting_user_id: uuid.UUID,
        page: int = 1,
        limit: int = 10,
        active_only: Optional[bool] = None,
        membership_active: Optional[bool] = None,
        roles: Optional[list[str]] = None,
    ) -> dict:
        """
        Get all users in an organization (paginated).

        Args:
            organization_id: Organization UUID
            requesting_user_id: UUID of the user requesting the data
            page: Page number (default: 1)
            limit: Items per page (default: 10)
            active_only: Only return active users (optional)
            membership_active: Filter by membership active status (optional)
            roles: List of role names to filter by (optional)

        Returns:
            dict: Dictionary with paginated users and metadata

        Raises:
            ValueError: If validation fails
        """
        logger.info(f"Fetching users for org_id={organization_id} by user_id={requesting_user_id}")

        try:
            organization = await OrganizationCRUD.get_by_id(self.db, organization_id)
            if not organization:
                raise ValueError("Organization not found")

            if organization.deleted_at:
                raise ValueError("Organization has been deleted")

            membership = await UserOrganizationCRUD.get_user_organization(
                self.db, requesting_user_id, organization_id
            )

            if not membership or not membership.is_active:
                raise ValueError("You do not have access to this organization")

            skip = (page - 1) * limit

            result = await UserOrganizationCRUD.get_all_users_in_organization(
                db=self.db,
                organization_id=organization_id,
                skip=skip,
                limit=limit,
                active_only=active_only,
                membership_active=membership_active,
                role_names=roles,
            )

            users = result["users"]
            total = result["total"]

            pagination = calculate_pagination(total=total, page=page, limit=limit)

            logger.info(f"Successfully retrieved {len(users)} users for org_id={organization_id}")

            return {"users": users, **pagination}

        except ValueError as e:
            logger.warning(
                f"Validation error fetching users for org_id={organization_id}: {str(e)}"
            )
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error fetching users for org_id={organization_id}: {str(e)}",
                exc_info=True,
            )
            raise Exception("Failed to retrieve organization users")

    async def delete_organization(
        self,
        organization_id: uuid.UUID,
        requesting_user_id: uuid.UUID,
    ) -> dict:
        """
        Delete an organization and all its associated data.

        Args:
            organization_id: Organization UUID to delete
            requesting_user_id: UUID of the user requesting deletion

        Returns:
            dict: Dictionary with deletion confirmation

        Raises:
            ValueError: If validation fails
            Exception: For unexpected errors
        """
        logger.info(
            f"Deleting organization org_id={organization_id} by user_id={requesting_user_id}"
        )

        try:
            has_permission = await check_user_permission(
                self.db, requesting_user_id, organization_id, "delete_organization"
            )

            if not has_permission:
                raise ValueError("You do not have permission to delete this organization")

            organization = await OrganizationCRUD.get_by_id(self.db, organization_id)
            if not organization:
                raise ValueError("Organization not found")

            if hasattr(organization, "deleted_at") and organization.deleted_at:
                raise ValueError("Organization is already deleted")

            user_role = await self.get_user_role_in_organization(
                requesting_user_id, organization_id
            )
            if user_role != "Owner":
                raise ValueError("Only organization owners can delete organizations")

            active_members_result = await UserOrganizationCRUD.get_all_users_in_organization(
                db=self.db, organization_id=organization_id, skip=0, limit=1000, active_only=True
            )

            active_members = active_members_result["users"]

            other_active_members = [
                m for m in active_members if m["user_id"] != str(requesting_user_id)
            ]

            if other_active_members:
                raise ValueError(
                    f"Cannot delete organization with {len(other_active_members)} active members. "
                    "Remove all other members first"
                )

            deletion_result = await OrganizationCRUD.delete_organization(self.db, organization_id)

            await self.db.commit()

            logger.info(f"Successfully deleted organization org_id={organization_id}")

            return {
                "organization_id": str(organization_id),
                "organization_name": organization.name,
                "deleted_at": deletion_result["deleted_at"],
            }

        except ValueError as e:
            logger.warning(
                f"Validation error deleting organization org_id={organization_id}: {str(e)}"
            )
            await self.db.rollback()
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error deleting organization org_id={organization_id}: {str(e)}",
                exc_info=True,
            )
            await self.db.rollback()
            raise Exception("Failed to delete organization")

    async def get_organization_invitations(
        self,
        organization_id: uuid.UUID,
        requesting_user_id: uuid.UUID,
        page: int = 1,
        limit: int = 10,
        status_filter: Optional[str] = "pending",
    ) -> dict:
        """
        Get all invitations for an organization (paginated).

        Args:
            organization_id: Organization UUID
            requesting_user_id: UUID of the user requesting the data
            page: Page number (default: 1)
            limit: Items per page (default: 10)
            status_filter: Filter by status (default: "pending", use "all" for no filter)

        Returns:
            dict: Dictionary with paginated invitations and metadata

        Raises:
            ValueError: If validation fails
        """
        logger.info(
            f"Fetching invitations for org_id={organization_id} by user_id={requesting_user_id}"
        )

        try:
            organization = await OrganizationCRUD.get_by_id(self.db, organization_id)
            if not organization:
                raise ValueError("Organization not found")

            if hasattr(organization, "deleted_at") and organization.deleted_at:
                raise ValueError("Organization has been deleted")

            membership = await UserOrganizationCRUD.get_user_organization(
                self.db, requesting_user_id, organization_id
            )

            if not membership or not membership.is_active:
                raise ValueError("You do not have access to this organization")

            has_manage = await check_user_permission(
                self.db, requesting_user_id, organization_id, "manage_users"
            )
            has_invite = await check_user_permission(
                self.db, requesting_user_id, organization_id, "invite_users"
            )

            if not (has_manage or has_invite):
                raise ValueError(
                    "You do not have permission to view invitations for this organization"
                )

            skip = (page - 1) * limit

            result = await InvitationCRUD.get_organization_invitations(
                db=self.db,
                organization_id=organization_id,
                skip=skip,
                limit=limit,
                status_filter=status_filter,
            )

            invitations = result["invitations"]
            total = result["total"]

            pagination = calculate_pagination(total=total, page=page, limit=limit)

            logger.info(
                f"Successfully retrieved {len(invitations)}invitations for org_id={organization_id}"
            )

            return {"invitations": invitations, **pagination}

        except ValueError as e:
            logger.warning(
                f"Validation error fetching invitations for org_id={organization_id}: {str(e)}"
            )
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error fetching invitations for org_id={organization_id}: {str(e)}",
                exc_info=True,
            )
            raise Exception("Failed to retrieve organization invitations")
