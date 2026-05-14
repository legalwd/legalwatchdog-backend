import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional, cast
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.core.config import settings
from app.api.core.dependencies.send_api_key import hash_api_key, send_api_key_email
from app.api.core.logger import setup_logging
from app.api.modules.v1.api_access.enums.api_key_scope import Scopes
from app.api.modules.v1.api_access.models.api_key_model import APIKey
from app.api.modules.v1.api_access.service.api_key_crud import APIKeyCRUD
from app.api.modules.v1.api_access.service.api_token_crud import create_api_key_onboarding_token
from app.api.utils.permissions import Permission, PermissionChecker

setup_logging()
logger = logging.getLogger("app")


class APIKeyService:
    def __init__(self, crud: APIKeyCRUD):
        self.crud = crud

    async def generate_and_hash_api_key(
        self,
        db: AsyncSession,
        key_name,
        organization_id,
        generated_by,
        scopes: list,
        user_id=None,
        receiver_email=None,
        expires_at=None,
    ) -> tuple[APIKey, str]:
        """
        Generate a new API key, hash it, and store it in DB.
        Returns a tuple (APIKey instance, raw_key_string).
        """
        raw_key = uuid4().hex
        hashed_key = hash_api_key(raw_key)

        if expires_at is None:
            expires_at = datetime.now(timezone.utc) + timedelta(
                days=settings.API_KEY_DEFAULT_EXPIRATION_DAYS
            )

        api_key_data = {
            "key_name": key_name,
            "organization_id": organization_id,
            "user_id": user_id,
            "hashed_key": hashed_key,
            "scope": ",".join(scopes),
            "generated_by": generated_by,
            "is_active": True,
            "created_at": datetime.now(timezone.utc),
            "expires_at": expires_at,
            "receiver_email": receiver_email,
        }

        api_key = await self.crud.create_key(db, **api_key_data)
        logger.info(f"Generated new API key {api_key.id} for organization {organization_id}")
        return api_key, raw_key

    def can_generate_key(self, user_permissions: dict) -> bool:
        """
        Determine if a user has permission to generate an API key.

        Args:
            user_permissions (dict): The user's permissions dictionary.

        Returns:
            bool: True if user can generate, False otherwise.
        """
        return PermissionChecker.has_permission(user_permissions, Permission.MANAGE_API_KEYS)

    def can_edit_scope(self, user_permissions: dict) -> bool:
        """Only admins and owners can edit scopes"""
        return PermissionChecker.has_permission(user_permissions, Permission.MANAGE_API_KEYS)

    def can_edit_expiration(self, user_permissions: dict) -> bool:
        """Only owner and admin can set expiration beyond defaults"""
        return PermissionChecker.has_permission(user_permissions, Permission.MANAGE_API_KEYS)

    def can_revoke_key(self, user_permissions: dict) -> bool:
        """Only owner and admin can revoke API key"""
        return PermissionChecker.has_permission(user_permissions, Permission.MANAGE_API_KEYS)

    def validate_scope(self, requested_scopes: list[str]) -> bool:
        """
        Validate that all requested scopes exist in the Scopes enum.

        Args:
            requested_scopes (list[str]): List of requested scopes.

        Returns:
            bool: True if all scopes are valid, raises ValueError otherwise.
        """
        valid_scopes = {scope.value for scope in Scopes}
        invalid = [s for s in requested_scopes if s not in valid_scopes]
        if invalid:
            raise ValueError(
                f"The following scope(s) are not valid: {', '.join(invalid)}. "
                "Please check the API documentation for available scopes."
            )
        return True

    def expires_at(self, provided: Optional[datetime] = None) -> datetime:
        """
        Determine the expiration datetime for a new API key.

        Args:
            provided (datetime, optional): The user-provided expiration time.

        Returns:
            datetime: The final expiration datetime.
        """
        now = datetime.now(timezone.utc)
        default_exp = now + timedelta(days=settings.API_KEY_DEFAULT_EXPIRATION_DAYS)
        max_exp = now + timedelta(days=settings.API_KEY_MAX_EXPIRATION_DAYS)

        final_exp = provided or default_exp

        if final_exp > max_exp:
            raise ValueError(
                f"Expiration cannot exceed {settings.API_KEY_MAX_EXPIRATION_DAYS} days from now"
            )

        return final_exp

    async def last_used_update(self, db: AsyncSession, api_key_id: UUID) -> None:
        """
        Update the 'last_used_at' timestamp of an API key to the current UTC time.

        Args:
            db (AsyncSession): Async DB session.
            api_key_id (UUID): ID of the API key being used.
        """
        now = datetime.now(timezone.utc)
        stmt = (
            update(APIKey)
            .where(cast(Any, APIKey.id) == api_key_id)
            .values(last_used_at=now)
            .execution_options(synchronize_session="fetch")
        )
        await db.execute(stmt)
        await db.commit()

    async def api_key_rotation(self, db: AsyncSession, api_key_id: UUID) -> str:
        """
        Replace an existing API key with a new one.
        Returns the new *raw* API key (only once).
        """

        result = await db.execute(select(APIKey).where(cast(Any, APIKey.id) == api_key_id))
        api_key = result.scalars().first()

        if not api_key:
            raise ValueError("API key not found")

        if not api_key.rotation_enabled:
            raise PermissionError("Rotation is disabled for this API key")

        now = datetime.now(timezone.utc)
        window_days = api_key.rotation_interval_days or settings.API_KEY_ROTATION_WINDOW_DAYS
        if api_key.last_rotated_at and api_key.last_rotated_at >= now - timedelta(days=window_days):
            logger.info(
                f"Skipping rotation for {api_key_id}: recently rotated at {api_key.last_rotated_at}"
            )
            return ""

        scopes = api_key.scope.split(",") if api_key.scope else []

        new_api_key, raw_key = await self.generate_and_hash_api_key(
            db=db,
            key_name=api_key.key_name,
            organization_id=api_key.organization_id,
            generated_by=api_key.generated_by,
            scopes=scopes,
            user_id=getattr(api_key, "user_id", None),
            receiver_email=getattr(api_key, "receiver_email", None),
            expires_at=None,
        )

        now_ts = datetime.now(timezone.utc)
        await self.crud.update_key(
            db,
            new_api_key.id,
            rotation_enabled=True,
            rotation_interval_days=api_key.rotation_interval_days,
            last_rotated_at=now_ts,
        )
        await self.crud.update_key(db, api_key_id, rotation_enabled=False)

        logger.info(
            f"Rotated API key {api_key_id} -> {new_api_key.id} for org {api_key.organization_id}"
        )

        return raw_key

    async def api_key_revocation(self, db: AsyncSession, api_key_id: UUID) -> None:
        """API Key Revocation When to revoke:

        Key is compromised

        User leaves organization

        Permissions change and old key is no longer valid
        """
        result = await db.execute(select(APIKey).where(cast(Any, APIKey.id) == api_key_id))
        api_key = result.scalars().first()
        if not api_key:
            raise ValueError("API key not found")

        stmt = update(APIKey).where(cast(Any, APIKey.id) == api_key_id).values(is_active=False)
        await db.execute(stmt)
        await db.commit()
        logger.info(f"API key {api_key_id} revoked.")

    async def find_keys_for_rotation(self, db: AsyncSession) -> list[APIKey]:
        """
        Return APIKey objects that are enabled for rotation and are within their rotation window.
        This loads all rotation-enabled keys and filters by each keys rotation_interval_days.
        """
        now = datetime.now(timezone.utc)
        stmt = select(APIKey).where(APIKey.rotation_enabled, APIKey.is_active)
        result = await db.execute(stmt)
        candidates = result.scalars().all()

        latest_by_name: dict[tuple[UUID, str], APIKey] = {}
        for k in candidates:
            key = (k.organization_id, k.key_name)
            existing = latest_by_name.get(key)
            if not existing:
                latest_by_name[key] = k
            else:
                if getattr(k, "created_at", None) and getattr(existing, "created_at", None):
                    if k.created_at > existing.created_at:
                        latest_by_name[key] = k
                else:
                    latest_by_name[key] = k

        due: list[APIKey] = []
        for k in latest_by_name.values():
            window_days = (
                k.rotation_interval_days
                or getattr(settings, "API_KEY_ROTATION_WINDOW_DAYS", None)
                or 3
            )
            if k.expires_at and k.expires_at <= now + timedelta(days=window_days):
                if k.last_rotated_at and k.last_rotated_at >= now - timedelta(days=window_days):
                    continue
                due.append(k)

        return due

    async def send_api_key_onboarding_email(
        self,
        db: AsyncSession,
        api_key: APIKey,
        expires_in_hours: int = 24,
    ):
        """
        Create onboarding token and send email with frontend URL.
        """
        token_obj = await create_api_key_onboarding_token(api_key, db, expires_in_hours)
        await send_api_key_email(api_key, token_obj, db)
