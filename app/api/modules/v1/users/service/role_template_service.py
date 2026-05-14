import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.modules.v1.users.models.role_template_model import RoleTemplate

logger = logging.getLogger("app")


class RoleTemplateCRUD:
    """CRUD operations for RoleTemplate model."""

    @staticmethod
    async def get_template_by_name(db: AsyncSession, template_name: str) -> Optional[RoleTemplate]:
        """Get role template by name."""
        try:
            result = await db.execute(
                select(RoleTemplate).where(RoleTemplate.name == template_name)
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error fetching template by name={template_name}: {str(e)}")
            raise

    @staticmethod
    async def get_all_templates(db: AsyncSession) -> list[RoleTemplate]:
        """Get all role templates."""
        try:
            result = await db.execute(
                select(RoleTemplate).order_by(RoleTemplate.hierarchy_level.desc())
            )
            return list(result.scalars().all())
        except Exception as e:
            logger.error(f"Error fetching all templates: {str(e)}")
            raise

    @staticmethod
    async def get_template_permissions(db: AsyncSession, template_name: str) -> dict:
        """Get permissions dict from template."""
        template = await RoleTemplateCRUD.get_template_by_name(db, template_name)
        if not template:
            logger.warning(f"Role template not found: template_name={template_name}")
            raise ValueError(
                "The role template you're looking for doesn't exist. "
                "Please contact your administrator."
            )
        return template.permissions

    @staticmethod
    async def create_custom_template(
        db: AsyncSession,
        name: str,
        display_name: str,
        permissions: dict,
        description: Optional[str] = None,
        hierarchy_level: int = 0,
    ) -> RoleTemplate:
        """Create a custom role template (non-system)."""
        try:
            template = RoleTemplate(
                name=name,
                display_name=display_name,
                description=description,
                permissions=permissions,
                is_system=False,
                hierarchy_level=hierarchy_level,
            )
            db.add(template)
            await db.flush()
            await db.refresh(template)
            return template
        except Exception as e:
            logger.error(f"Error creating custom template: {str(e)}")
            raise
