from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.api.modules.v1.auth.schemas.role import RoleCreateRequest
from app.api.modules.v1.users.models.roles_model import Role
from app.api.modules.v1.users.models.users_model import User


async def create_role(db: AsyncSession, org_id, data: RoleCreateRequest) -> Role:
    role = Role(
        name=data.name,
        description=data.description,
        permissions=data.permissions,
        organization_id=org_id,
    )
    db.add(role)
    await db.commit()
    await db.refresh(role)
    return role


async def assign_role_to_user(db: AsyncSession, user_id, role_id) -> Optional[User]:
    user = await db.scalar(select(User).where(User.id == user_id))
    if not user:
        return None
    user.role_id = role_id
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user
