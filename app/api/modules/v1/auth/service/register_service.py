import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import BackgroundTasks
from redis.asyncio.client import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.core.config import settings
from app.api.core.custom_exceptions.exceptions import (
    InvalidOTPError,
    NotFoundError,
    ProcessingError,
    RateLimitExceededError,
    RegistrationPendingError,
    UserAlreadyRegisteredError,
)
from app.api.core.dependencies.redis_service import check_rate_limit
from app.api.core.dependencies.send_mail import send_email
from app.api.modules.v1.auth.schemas.register import RegisterRequest
from app.api.modules.v1.organization.models.invitation_model import InvitationStatus
from app.api.modules.v1.organization.service.invitation_service import InvitationCRUD
from app.api.modules.v1.organization.service.user_organization_service import UserOrganizationCRUD
from app.api.modules.v1.users.service.user import UserCRUD
from app.api.utils.generate_otp import generate_code
from app.api.utils.organization_validations import (
    validate_no_pending_registration,
)
from app.api.utils.password import hash_password
from app.api.utils.redis import (
    delete_user_credentials,
    get_user_credentials,
    store_user_credentials,
    verify_and_get_credentials,
)

logger = logging.getLogger("app")


class RegistrationService:
    """
    Service class to handle company registration business logic.

    Attributes:
        db: Async database session for data operations
        redis_client: Redis client for caching and temporary storage
    """

    def __init__(self, db: AsyncSession, redis_client: Redis):
        """
        Initialize registration service.

        Args:
            db: Async database session
            redis_client: Redis client instance
        """
        self.db = db
        self.redis_client = redis_client

    async def register_user(
        self,
        payload: RegisterRequest,
        background_tasks: BackgroundTasks,
        token: Optional[str] = None,
    ) -> dict:
        """
        Handle the complete user registration process.

        This method validates the registration request, generates OTP,
        stores credentials temporarily in Redis, and sends verification email.

        Args:
            payload: Registration request containing user's organizational email and password
            background_tasks: Optional FastAPI background tasks for async email sending

        Returns:
            dict: Dictionary containing the registered email address

        Raises:
            ValueError: If validation fails (duplicate email or pending registration)
            Exception: For unexpected errors during registration process
        """
        logger.info("Starting user signup for email=%s", payload.email)

        try:
            existing_user = await UserCRUD.get_by_email(self.db, payload.email)
            if existing_user:
                raise UserAlreadyRegisteredError()

            await validate_no_pending_registration(self.redis_client, payload.email)

            otp_code = generate_code()
            hashed_pw = hash_password(payload.password)
            logger.info(f"otp: {otp_code}")

            registration_data = {
                "name": payload.name,
                "email": payload.email,
                "hashed_password": hashed_pw,
                "otp_code": otp_code,
            }
            if token:
                registration_data["token"] = token

            await store_user_credentials(
                redis_client=self.redis_client,
                email=payload.email,
                registration_data=registration_data,
                ttl_seconds=settings.REDIS_REGISTER_TTL,
            )

            await self._send_otp_email(
                payload.email, otp_code, background_tasks, settings.REDIS_REGISTER_TTL
            )

            logger.info("Successfully initiated user registration for email=%s", payload.email)

            return {"email": payload.email}

        except (UserAlreadyRegisteredError, ProcessingError):
            raise
        except Exception as e:
            logger.error(
                "Unexpected error during registration for email=%s: %s",
                payload.email,
                str(e),
                exc_info=True,
            )
            raise ProcessingError(
                message=("An error occurred during registration. Please try again.")
            )

    async def verify_otp_and_complete_registration(
        self, email: str, code: str, background_tasks: BackgroundTasks = None
    ) -> dict:
        """
        Verify OTP and complete the organization registration.

        This method verifies the OTP code, retrieves stored registration data,
        creates the organization, admin role, and admin user, then cleans up Redis.

        Args:
            email: User email address
            code: OTP code to verify

        Returns:
            dict: Dictionary containing organization and user details

        Raises:
            ValueError: If OTP is invalid, expired, or registration not found
            Exception: For unexpected errors during registration completion
        """
        logger.info("Starting OTP verification for email=%s", email)

        try:
            credentials = await verify_and_get_credentials(
                redis_client=self.redis_client, email=email, otp_code=code
            )

            if not credentials:
                logger.warning("Invalid OTP or registration not found for email=%s", email)
                raise InvalidOTPError()

            user_crud = UserCRUD(self.db)
            user = await user_crud.create_user(
                name=credentials["name"],
                email=credentials["email"],
                hashed_password=credentials["hashed_password"],
                is_verified=True,
                is_approved=False,
            )
            logger.info("Created user with id=%s", user.id)

            if "token" in credentials:
                token = credentials["token"]
                invitation = await InvitationCRUD.get_invitation_by_token(self.db, token)

                if not invitation:
                    logger.warning(
                        f"Token {token} not found during registration for user {user.id}"
                    )
                elif (
                    invitation.status != InvitationStatus.PENDING
                    or invitation.expires_at < datetime.now(timezone.utc)
                ):
                    logger.warning(
                        f"Invitation {invitation.id} is not pending/has expired for user {user.id}"
                    )
                elif user.email.lower() != invitation.invited_email.lower():
                    logger.warning(
                        f"Email mismatch during registration: registered={user.email}, "
                        f"invited={invitation.invited_email}, token={token}"
                    )
                else:
                    await UserOrganizationCRUD.add_user_to_organization(
                        db=self.db,
                        user_id=user.id,
                        organization_id=invitation.organization_id,
                        role_id=invitation.role_id,
                        is_active=True,
                    )
                    await InvitationCRUD.update_invitation_status(
                        self.db,
                        invitation.id,
                        InvitationStatus.ACCEPTED,
                        accepted_at=datetime.now(timezone.utc),
                    )
                    logger.info(
                        f"{user.id} added, org {invitation.organization_id}, invite {invitation.id}"
                    )

            await delete_user_credentials(redis_client=self.redis_client, email=email)
            logger.info("Cleaned up pending registration for email=%s", email)

            await self.db.commit()

            # Send pending approval email notification
            if background_tasks:
                background_tasks.add_task(
                    send_email,
                    "account_pending_approval.html",
                    "Your Account is Pending Approval",
                    user.email,
                    {"full_name": user.name},
                )
                logger.info("Queued pending approval email for user_id=%s", user.id)

                background_tasks.add_task(
                    send_email,
                    "new_user_registration_admin_notification.html",
                    f"New User Registration: {user.name} - Pending Approval",
                    settings.ADMIN_EMAIL,
                    {
                        "user_name": user.name,
                        "user_email": user.email,
                        "registered_at": datetime.now(timezone.utc).strftime(
                            "%Y-%m-%d %H:%M:%S UTC"
                        ),
                        "dashboard_url": f"{settings.FRONTEND_URL}/super-admin/customers",
                    },
                )
                logger.info(
                    "Queued admin notification for new user registration user_id=%s",
                    user.id,
                )

            logger.info("Successfully completed registration for email=%s", email)

            return {
                "email": user.email,
                "user_id": user.id,
                "message": "Registration completed successfully.",
            }

        except (InvalidOTPError, ProcessingError):
            raise
        except Exception as e:
            logger.error(
                "Unexpected error during registration completion for email=%s: %s",
                email,
                str(e),
                exc_info=True,
            )
            await self.db.rollback()
            raise ProcessingError(
                message="An error occurred during registration completion. Please try again."
            )

    async def _send_otp_email(
        self,
        email: str,
        otp_code: str,
        background_tasks: BackgroundTasks,
        expiry_seconds: Optional[int] = None,
    ) -> None:
        """
        Send OTP verification email to user.

        Sends email as a background task (non-blocking)
        depending on whether background_tasks is provided.

        Args:
            email: Recipient email address
            otp_code: Generated OTP code to send
            background_tasks: background tasks handler for async sending
        """
        expiry_seconds = expiry_seconds or settings.REDIS_REGISTER_TTL
        otp_expiry_minutes = expiry_seconds // 60
        context = {"email": email, "otp": otp_code, "otp_expiry_minutes": otp_expiry_minutes}

        background_tasks.add_task(send_email, "otp.html", "OTP for Registration", email, context)
        logger.debug("OTP email queued for background sending to %s", email)

    async def resend_otp(
        self,
        email: str,
        background_tasks: BackgroundTasks,
    ) -> dict:
        """
        Resend registration OTP for a pending user signup.

        Args:
            email: Email address used for the original registration.
            background_tasks: FastAPI background task handler for sending email asynchronously.

        Returns:
            dict: Dictionary containing the email for which the OTP was resent.

        Raises:
            ValueError: If the email belongs to an already registered organization
                        or there is no pending registration for the email.
            Exception: For unexpected errors during the resend process.
        """
        logger.info("Starting resend OTP for email=%s", email)

        try:
            existing_user = await UserCRUD.get_by_email(self.db, email)
            if existing_user:
                logger.warning("Resend OTP requested for already registered email=%s", email)
                raise UserAlreadyRegisteredError(
                    message="User already registered. Please log in instead."
                )

            credentials = await get_user_credentials(self.redis_client, email)

            if not credentials:
                logger.warning("No pending registration found for email=%s", email)
                raise NotFoundError(
                    message="No pending registration found for this email. Please sign up again."
                )

            otp_code = generate_code()
            credentials["otp_code"] = otp_code

            await store_user_credentials(
                redis_client=self.redis_client,
                email=email,
                registration_data=credentials,
                ttl_seconds=settings.REDIS_RESEND_TTL,
            )

            await self._send_otp_email(email, otp_code, background_tasks, settings.REDIS_RESEND_TTL)

            logger.info("Resent OTP successfully for email=%s", email)

            return {"email": email}

        except (UserAlreadyRegisteredError, NotFoundError, ProcessingError):
            raise
        except Exception as e:
            logger.error(
                "Unexpected error during resend OTP for email=%s: %s",
                email,
                str(e),
                exc_info=True,
            )
            raise ProcessingError(
                message=("An error occurred while resending OTP. Please try again.")
            )

    async def register_user_with_validation(
        self,
        payload: RegisterRequest,
        background_tasks: BackgroundTasks,
        token: Optional[str] = None,
    ) -> dict:
        try:
            existing_user = await UserCRUD.get_by_email(self.db, payload.email)
            if existing_user:
                raise UserAlreadyRegisteredError(
                    message="An account with this email already exists. Please log in instead."
                )

            try:
                await validate_no_pending_registration(self.redis_client, payload.email)
            except ValueError:
                raise RegistrationPendingError(
                    message=(
                        "A pending registration already exists for this email. "
                        "Please check your inbox or try again later."
                    )
                )

            return await self.register_user(payload, background_tasks, token)

        except (UserAlreadyRegisteredError, RegistrationPendingError):
            raise
        except Exception as e:
            logger.error(
                "Unexpected error during registration for email=%s: %s",
                payload.email,
                str(e),
                exc_info=True,
            )
            raise ProcessingError(
                message=(
                    "We're unable to process your registration right now. Please try again later."
                )
            )

    async def verify_otp_with_rate_limit(
        self,
        email: str,
        code: str,
        ip_address: Optional[str] = None,
        background_tasks: BackgroundTasks = None,
    ) -> dict:
        MAX_OTP_VERIFY_ATTEMPTS = 5
        IP_RATE_LIMIT_MULTIPLIER = 3
        RATE_LIMIT_WINDOW_SECONDS = 3600

        try:
            email_allowed = await check_rate_limit(
                f"otp_verify:email:{email}",
                max_attempts=MAX_OTP_VERIFY_ATTEMPTS,
                window_seconds=RATE_LIMIT_WINDOW_SECONDS,
            )

            if not email_allowed:
                raise RateLimitExceededError(
                    message=(
                        "Too many OTP verification attempts for this email. Please retry in 1 hour."
                    )
                )

            if ip_address:
                ip_allowed = await check_rate_limit(
                    f"otp_verify:ip:{ip_address}",
                    max_attempts=MAX_OTP_VERIFY_ATTEMPTS * IP_RATE_LIMIT_MULTIPLIER,
                    window_seconds=RATE_LIMIT_WINDOW_SECONDS,
                )

                if not ip_allowed:
                    raise RateLimitExceededError(
                        message=(
                            "Too many OTP verification attempts from this IP. "
                            "Please retry in 1 hour."
                        )
                    )

            return await self.verify_otp_and_complete_registration(
                email=email, code=code, background_tasks=background_tasks
            )

        except RateLimitExceededError:
            raise
        except (InvalidOTPError, ProcessingError):
            raise
        except Exception as e:
            logger.error(
                "Unexpected error during OTP verification for email=%s: %s",
                email,
                str(e),
                exc_info=True,
            )
            raise ProcessingError(
                message="We're unable to verify your code right now. Please try again later."
            )

    async def resend_otp_with_rate_limit(
        self,
        email: str,
        background_tasks: BackgroundTasks,
        ip_address: Optional[str] = None,
    ) -> dict:
        MAX_OTP_REQUEST_ATTEMPTS = 3
        IP_RATE_LIMIT_MULTIPLIER = 3
        RATE_LIMIT_WINDOW_SECONDS = 3600

        try:
            email_allowed = await check_rate_limit(
                f"otp_request:email:{email}",
                max_attempts=MAX_OTP_REQUEST_ATTEMPTS,
                window_seconds=RATE_LIMIT_WINDOW_SECONDS,
            )

            if not email_allowed:
                raise RateLimitExceededError(
                    message="Too many OTP requests for this email. Please retry in 1 hour."
                )

            if ip_address:
                ip_allowed = await check_rate_limit(
                    f"otp_request:ip:{ip_address}",
                    max_attempts=MAX_OTP_REQUEST_ATTEMPTS * IP_RATE_LIMIT_MULTIPLIER,
                    window_seconds=RATE_LIMIT_WINDOW_SECONDS,
                )

                if not ip_allowed:
                    raise RateLimitExceededError(
                        message="Too many OTP requests from this IP. Please retry in 1 hour."
                    )

            return await self.resend_otp(email=email, background_tasks=background_tasks)

        except RateLimitExceededError:
            raise
        except (UserAlreadyRegisteredError, NotFoundError, ProcessingError):
            raise
        except Exception as e:
            logger.error(
                "Unexpected error during OTP resend for email=%s: %s",
                email,
                str(e),
                exc_info=True,
            )
            raise ProcessingError(
                message="We're unable to resend your code right now. Please try again later."
            )
