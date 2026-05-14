from typing import Any, cast
from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.modules.v1.api_access.models.api_key_model import APIKey


class APIKeyCRUD:
    """
    CRUD operations for APIKey model.
    Pure database operations; business logic (scope,
    role checks, expiration) should be in service layer.
    """

    async def get_key_by_id(self, db: AsyncSession, key_id: UUID) -> APIKey | None:
        """
        Retrieve a single APIKey by its ID.
        """
        result = await db.execute(select(APIKey).where(cast(Any, APIKey.id) == key_id))
        return result.scalars().first()

    async def create_key(self, db: AsyncSession, **kwargs) -> APIKey:
        """
        Create a new APIKey record.
        kwargs should include all required model fields.
        """
        obj = APIKey(**kwargs)
        db.add(obj)
        await db.commit()
        await db.refresh(obj)
        return obj

    async def update_key(self, db: AsyncSession, key_id: UUID, **kwargs) -> APIKey | None:
        """
        Update fields of an existing APIKey.
        Returns the updated object, or None if it doesn't exist.
        """
        if not kwargs:
            return await self.get_key_by_id(db, key_id)

        stmt = (
            update(APIKey)
            .where(cast(Any, APIKey.id) == key_id)
            .values(**kwargs)
            .execution_options(synchronize_session="fetch")
        )
        await db.execute(stmt)
        await db.commit()
        return await self.get_key_by_id(db, key_id)

    async def delete_key(self, db: AsyncSession, key_id: UUID, soft_delete: bool = True) -> bool:
        """
        Delete an APIKey by ID.
        By default, performs a soft delete (is_active=False).
        Set soft_delete=False to hard delete the record.
        Returns True if operation completed.
        """
        if soft_delete:
            stmt = (
                update(APIKey)
                .where(cast(Any, APIKey.id) == key_id)
                .values(is_active=False)
                .execution_options(synchronize_session="fetch")
            )
            await db.execute(stmt)
        else:
            stmt = delete(APIKey).where(cast(Any, APIKey.id) == key_id)
            await db.execute(stmt)

        await db.commit()
        return True

    async def count_keys_by_org(self, db: AsyncSession, organization_id: UUID) -> int:
        """
        Return number of API keys in an organization.
        """
        stmt = (
            select(func.count())
            .select_from(APIKey)
            .where(cast(Any, APIKey.organization_id) == organization_id)
        )
        result = await db.execute(stmt)
        return int(result.scalar() or 0)

    async def get_keys_by_org_paginated(
        self, db: AsyncSession, organization_id: UUID, offset: int = 0, limit: int = 20
    ) -> list[APIKey]:
        """
        Return paginated APIKey objects for an organization.
        """
        stmt = (
            select(APIKey)
            .where(cast(Any, APIKey.organization_id) == organization_id)
            .offset(int(offset))
            .limit(int(limit))
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())
