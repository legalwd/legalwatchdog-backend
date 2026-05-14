import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import func, select

from app.api.core.config import settings
from app.api.modules.v1.organization.models.invitation_model import Invitation, InvitationStatus

logger = logging.getLogger("app")


class InvitationCRUD:
    """CRUD operations for Invitation model."""

    @staticmethod
    async def create_invitation(
        db: AsyncSession,
        organization_id: uuid.UUID,
        organization_name: str,
        invited_email: str,
        inviter_id: uuid.UUID,
        token: str,
        role_id: Optional[uuid.UUID] = None,
        role_name: Optional[str] = None,
        status: InvitationStatus = InvitationStatus.PENDING,
    ) -> Invitation:
        """
        Create a new invitation.
        """
        try:
            invitation = Invitation(
                organization_id=organization_id,
                organization_name=organization_name,
                invited_email=invited_email,
                inviter_id=inviter_id,
                token=token,
                role_id=role_id,
                role_name=role_name,
                status=status,
            )

            logger.info(
                "Created invitation: id=%s, org_id=%s, invited_email=%s, token=%s",
                invitation.id,
                invitation.organization_id,
                invitation.invited_email,
                token,
            )
            db.add(invitation)
            await db.flush()
            await db.refresh(invitation)
            logger.info(
                "Created invitation: id=%s, org_id=%s, invited_email=%s",
                invitation.id,
                invitation.organization_id,
                invitation.invited_email,
            )
            return invitation
        except Exception as e:
            logger.error("Failed to create invitation for email=%s: %s", invited_email, str(e))
            raise Exception("Failed to create invitation")

    @staticmethod
    async def get_invitation_by_token(db: AsyncSession, token: str) -> Optional[Invitation]:
        """
        Get an invitation by its token.
        """
        result = await db.execute(select(Invitation).where(Invitation.token == token))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_pending_invitation_for_email_and_org(
        db: AsyncSession,
        email: str,
        organization_id: uuid.UUID,
    ) -> Optional[Invitation]:
        """
        Check if a pending (non-expired) invitation already exists for an email and organization.

        Args:
            db: Database session
            email: Email address to check
            organization_id: Organization UUID

        Returns:
            Invitation if a pending one exists, None otherwise
        """
        result = await db.execute(
            select(Invitation).where(
                Invitation.invited_email == email,
                Invitation.organization_id == organization_id,
                Invitation.status == InvitationStatus.PENDING,
                Invitation.expires_at > datetime.now(timezone.utc),
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def update_invitation_status(
        db: AsyncSession,
        invitation_id: uuid.UUID,
        status: InvitationStatus,
        accepted_at: Optional[datetime] = None,
    ) -> Invitation:
        """
        Update the status of an invitation.
        """
        try:
            invitation = await db.get(Invitation, invitation_id)
            if not invitation:
                logger.warning(f"Invitation not found: invitation_id={invitation_id}")
                raise ValueError("The invitation you're looking for doesn't exist.")
            invitation.status = status
            invitation.updated_at = datetime.now(timezone.utc)

            if status == InvitationStatus.ACCEPTED and accepted_at:
                invitation.accepted_at = accepted_at

            db.add(invitation)
            await db.flush()
            await db.refresh(invitation)
            logger.info("Updated invitation %s status to %s", invitation_id, status)
            return invitation

        except Exception as e:
            logger.error("Failed to update invitation %s: %s", invitation_id, str(e))
            await db.rollback()
            raise Exception("Failed to update invitation")

    @staticmethod
    async def get_pending_invitations_for_user_email(
        db: AsyncSession, email: str, page: int = 1, limit: int = 20
    ) -> tuple[list[Invitation], int]:
        """
        Get all pending invitations for a specific email address with pagination.
        """

        try:
            conditions = (
                Invitation.invited_email == email,
                Invitation.status == InvitationStatus.PENDING,
                Invitation.expires_at > datetime.now(timezone.utc),
            )

            count_stmt = select(func.count()).select_from(Invitation).where(*conditions)
            total_result = await db.execute(count_stmt)
            total = total_result.scalar() or 0

            stmt = (
                select(Invitation)
                .where(*conditions)
                .order_by(Invitation.created_at.desc())
                .offset((page - 1) * limit)
                .limit(limit)
            )

            result = await db.execute(stmt)
            invitations = list(result.scalars().all())

            return invitations, total

        except Exception as e:
            logger.error("Failed to get pending invitations for email=%s: %s", email, str(e))
            raise Exception("Failed to get invitations")

    @staticmethod
    async def _is_invitation_expired(invitation: Invitation) -> bool:
        """
        Check if an invitation has expired.
        """
        return invitation.expires_at < datetime.now(timezone.utc)

    @staticmethod
    async def expire_invitation(db: AsyncSession, invitation_id: uuid.UUID) -> Invitation:
        """
        Explicitly expire an invitation.
        """
        return await InvitationCRUD.update_invitation_status(
            db, invitation_id, InvitationStatus.EXPIRED
        )

    @staticmethod
    async def get_organization_invitations(
        db: AsyncSession,
        organization_id: uuid.UUID,
        skip: int = 0,
        limit: int = 10,
        status_filter: Optional[str] = None,
    ) -> dict:
        """
        Get all invitations for an organization with pagination and filtering.

        Args:
            db: Database session
            organization_id: Organization UUID
            skip: Number of records to skip
            limit: Maximum number of records to return
            status_filter: Optional status to filter by (e.g., 'pending', 'accepted', 'all')

        Returns:
            dict: Dictionary containing invitations list and total count
        """
        try:
            from app.api.modules.v1.users.models.users_model import User

            query = select(Invitation).where(Invitation.organization_id == organization_id)

            count_query = (
                select(func.count())
                .select_from(Invitation)
                .where(Invitation.organization_id == organization_id)
            )

            if status_filter and status_filter.lower() != "all":
                status_filter_upper = status_filter.upper()
                if hasattr(InvitationStatus, status_filter_upper):
                    status_enum = InvitationStatus[status_filter_upper]
                    query = query.where(Invitation.status == status_enum)
                    count_query = count_query.where(Invitation.status == status_enum)

            query = query.order_by(Invitation.created_at.desc())

            total_result = await db.execute(count_query)
            total = total_result.scalar() or 0

            query = query.offset(skip).limit(limit)

            result = await db.execute(query)
            invitations = result.scalars().all()

            formatted_invitations = []
            for invitation in invitations:
                inviter = await db.get(User, invitation.inviter_id)

                is_expired = invitation.expires_at < datetime.now(timezone.utc)

                formatted_invitations.append(
                    {
                        "id": str(invitation.id),
                        "organization_id": str(invitation.organization_id),
                        "organization_name": invitation.organization_name,
                        "invited_email": invitation.invited_email,
                        "inviter_id": str(invitation.inviter_id),
                        "inviter_name": inviter.name if inviter else "Unknown",
                        "inviter_email": inviter.email if inviter else None,
                        "role_id": str(invitation.role_id) if invitation.role_id else None,
                        "role_name": invitation.role_name,
                        "status": invitation.status.value,
                        "is_expired": is_expired,
                        "expires_at": invitation.expires_at.isoformat(),
                        "accepted_at": invitation.accepted_at.isoformat()
                        if invitation.accepted_at
                        else None,
                        "created_at": invitation.created_at.isoformat(),
                        "updated_at": invitation.updated_at.isoformat(),
                    }
                )

            logger.info(
                f"Retrieved {len(formatted_invitations)} invitations for org_id={organization_id}"
            )

            return {
                "invitations": formatted_invitations,
                "total": total,
            }

        except Exception as e:
            logger.error(
                f"Failed to get invitations for org_id={organization_id}: {str(e)}",
                exc_info=True,
            )
            raise Exception("Failed to retrieve invitations")

    @staticmethod
    async def cancel_invitation(
        db: AsyncSession,
        invitation_id: uuid.UUID,
        requesting_user_id: uuid.UUID,
    ) -> Invitation:
        """
        Cancel a pending invitation.

        Args:
            db: Database session
            invitation_id: Invitation UUID to cancel
            requesting_user_id: User requesting the cancellation

        Returns:
            Updated invitation object

        Raises:
            ValueError: If invitation not found or cannot be cancelled
        """
        try:
            invitation = await db.get(Invitation, invitation_id)
            if not invitation:
                logger.warning(f"Invitation not found: invitation_id={invitation_id}")
                raise ValueError("The invitation you're trying to cancel doesn't exist.")

            if invitation.status != InvitationStatus.PENDING:
                logger.warning(
                    f"Cannot cancel non-pending invitation: invitation_id={invitation_id}, "
                    f"status={invitation.status.value}"
                )
                raise ValueError(
                    "This invitation can't be cancelled because it's already been "
                    f"{invitation.status.value.lower()}."
                )

            invitation.status = InvitationStatus.CANCELLED
            invitation.updated_at = datetime.now(timezone.utc)

            db.add(invitation)
            await db.flush()
            await db.refresh(invitation)

            logger.info(f"Cancelled invitation {invitation_id} by user {requesting_user_id}")
            return invitation

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Failed to cancel invitation {invitation_id}: {str(e)}")
            raise Exception("Failed to cancel invitation")

    @staticmethod
    async def resend_invitation(
        db: AsyncSession,
        invitation_id: uuid.UUID,
        new_token: str,
    ) -> Invitation:
        """
        Resend an invitation by generating a new token and extending expiry.

        Args:
            db: Database session
            invitation_id: Invitation UUID to resend
            new_token: New unique token for the invitation

        Returns:
            Updated invitation object

        Raises:
            ValueError: If invitation cannot be resent
        """
        try:
            invitation = await db.get(Invitation, invitation_id)
            if not invitation:
                logger.warning(f"Invitation not found: invitation_id={invitation_id}")
                raise ValueError("The invitation you're trying to resend doesn't exist.")

            if invitation.status not in [InvitationStatus.PENDING, InvitationStatus.EXPIRED]:
                logger.warning(
                    f"Cannot resend non-pending/expired invitation: "
                    f"invitation_id={invitation_id}, status={invitation.status.value}"
                )
                raise ValueError(
                    "This invitation can't be resent because it's already been "
                    f"{invitation.status.value.lower()}."
                )

            invitation.token = new_token
            invitation.status = InvitationStatus.PENDING
            invitation.expires_at = datetime.now(timezone.utc) + timedelta(
                minutes=settings.INVITATION_TOKEN_EXPIRE_MINUTES
            )
            invitation.updated_at = datetime.now(timezone.utc)

            db.add(invitation)
            await db.flush()
            await db.refresh(invitation)

            logger.info(f"Resent invitation {invitation_id} with new token")
            return invitation

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Failed to resend invitation {invitation_id}: {str(e)}")
            raise Exception("Failed to resend invitation")

    @staticmethod
    async def accept_invitation(
        db: AsyncSession,
        token: str,
        current_user_id: Optional[uuid.UUID] = None,
        current_user_email: Optional[str] = None,
    ) -> dict:
        """
        Accept an organization invitation.

        Handles the complete invitation acceptance flow including:
        - Token validation
        - Expiration checking
        - Email verification (for authenticated users)
        - Organization membership creation
        - Status updates

        Args:
            db: Database session
            token: Invitation token
            current_user_id: Optional authenticated user ID
            current_user_email: Optional authenticated user email

        Returns:
            dict: Result containing accepted status, redirect URL (if unauthenticated),
                  or organization details (if authenticated)

        Raises:
            NotFoundError: If invitation not found or invalid.
            BadRequestError: If invitation is expired or already processed.
            PermissionDeniedError: If email mismatch during acceptance.
            AlreadyExistsError: If user is already a member of the organization.
        """
        from app.api.core.custom_exceptions.exceptions import (
            AlreadyExistsError,
            BadRequestError,
            NotFoundError,
            PermissionDeniedError,
        )
        from app.api.modules.v1.organization.service.user_organization_service import (
            UserOrganizationCRUD,
        )
        from app.api.modules.v1.users.service.role import RoleCRUD
        from app.api.modules.v1.users.service.user import UserCRUD

        try:
            invitation = await InvitationCRUD.get_invitation_by_token(db, token)
            if not invitation:
                raise NotFoundError(message="The invitation link is invalid or has been removed.")

            if invitation.status != InvitationStatus.PENDING:
                raise BadRequestError(
                    message=f"This invitation has already been {invitation.status.value.lower()}."
                )

            if invitation.expires_at < datetime.now(timezone.utc):
                await InvitationCRUD.update_invitation_status(
                    db, invitation.id, InvitationStatus.EXPIRED
                )
                await db.commit()
                raise BadRequestError(
                    message="This invitation has expired. Please request a new invitation."
                )

            user = await UserCRUD.get_by_email(db, invitation.invited_email)

            if user and current_user_id:
                if (
                    current_user_email
                    and current_user_email.lower() != invitation.invited_email.lower()
                ):
                    logger.warning(
                        f"Unauthorized invitation acceptance attempt: user={current_user_email}, "
                        f"invited={invitation.invited_email}, token={token}"
                    )
                    raise PermissionDeniedError(
                        message=(
                            "This invitation was sent to a different email address. "
                            "You can only accept invitations sent to your email."
                        )
                    )

                existing_membership = await UserOrganizationCRUD.get_user_organization(
                    db, current_user_id, invitation.organization_id
                )
                if existing_membership:
                    await InvitationCRUD.update_invitation_status(
                        db, invitation.id, InvitationStatus.ACCEPTED
                    )
                    await db.commit()
                    return {
                        "accepted": True,
                        "already_member": True,
                        "organization_id": str(invitation.organization_id),
                        "message": (
                            "You are already a member of this organization. Invitation accepted."
                        ),
                    }

                role_id = invitation.role_id
                if not role_id:
                    default_role = await RoleCRUD.get_default_user_role(
                        db, invitation.organization_id
                    )
                    role_id = default_role.id

                await UserOrganizationCRUD.add_user_to_organization(
                    db=db,
                    user_id=current_user_id,
                    organization_id=invitation.organization_id,
                    role_id=role_id,
                    is_active=True,
                )

                await InvitationCRUD.update_invitation_status(
                    db, invitation.id, InvitationStatus.ACCEPTED
                )
                await db.commit()

                logger.info(
                    f"Invitation accepted: user={current_user_email}, "
                    f"org_id={invitation.organization_id}, token={token}"
                )

                return {
                    "accepted": True,
                    "already_member": False,
                    "organization_id": str(invitation.organization_id),
                    "organization_name": invitation.organization_name,
                    "role_name": invitation.role_name,
                    "message": "Invitation accepted. You have been added to the organization.",
                }

            logger.info(
                "Unauthenticated/unregistered user for invitation token. "
                f"Requires registration for email: {invitation.invited_email}"
            )
            return {
                "requires_registration": True,
                "already_member": False,
                "organization_id": str(invitation.organization_id),
                "message": "Please register or log in to accept this invitation.",
            }

        except (NotFoundError, BadRequestError, PermissionDeniedError, AlreadyExistsError):
            raise
        except Exception as e:
            logger.error(f"Failed to accept invitation {token}: {str(e)}", exc_info=True)
            await db.rollback()
            from app.api.core.custom_exceptions.exceptions import ProcessingError

            raise ProcessingError(
                message="We're unable to process your invitation right now. Please try again later."
            )
