import logging
import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.modules.v1.users.models.roles_model import Role
from app.api.modules.v1.users.service.role_template_service import RoleTemplateCRUD

logger = logging.getLogger("app")


class RoleCRUD:
    """CRUD operations for Role model."""

    @staticmethod
    async def create_role_from_template(
        db: AsyncSession,
        organization_id: uuid.UUID,
        template_name: str,
        role_name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Role:
        """
        Create a role from template (JSON or hardcoded).

        Args:
            db: Async database session
            organization_id: UUID of the organization
            template_name: Name of the template ('owner', 'admin', etc.)
            custom_name: Optional custom name override
            custom_description: Optional custom description

        Returns:
            Role: Created role object

        Raises:
            Exception: If database operation fails
        """
        try:
            template = await RoleTemplateCRUD.get_template_by_name(db, template_name)
            if not template:
                logger.warning(f"Role template not found: template_name={template_name}")
                raise ValueError(
                    "The role template you're looking for doesn't exist. "
                    "Please contact your administrator."
                )

            final_name = role_name or template.display_name
            final_description = description or template.description
            role = Role(
                name=final_name,
                organization_id=organization_id,
                description=final_description,
                permissions=template.permissions.copy(),
                template_name=template_name,
                hierarchy_level=template.hierarchy_level,
            )

            db.add(role)
            await db.flush()
            await db.refresh(role)

            logger.info(
                "Created role from template: id=%s, name=%s, template=%s, org_id=%s, hierarchy=%s",
                role.id,
                role.name,
                template_name,
                organization_id,
                role.hierarchy_level,
            )

            return role

        except ValueError:
            raise

        except Exception as e:
            logger.error(
                "Failed to create role from template %s for organization_id=%s: %s",
                template_name,
                organization_id,
                str(e),
                exc_info=True,
            )
            raise Exception(f"Failed to create role from template '{template_name}'")

    @staticmethod
    async def create_owner_role(
        db: AsyncSession,
        organization_id: uuid.UUID,
        role_name: str = "Owner",
        description: Optional[str] = "Owner with full permissions",
    ) -> Role:
        """
        Create an owner role for an organization.

        Args:
            db: Async database session
            organization_id: UUID of the organization
            role_name: Name of the role (default: "Owner")
            description: Role description (optional)

        Returns:
            Role: Created role object

        Raises:
            ValueError: If owner role already exists for this organization
            Exception: If database operation fails
        """
        return await RoleCRUD.create_role_from_template(
            db=db,
            organization_id=organization_id,
            template_name="owner",
            role_name=role_name,
            description=description or "Organization owner with full permissions",
        )

    @staticmethod
    async def create_admin_role(
        db: AsyncSession,
        organization_id: uuid.UUID,
        role_name: str = "Admin",
        description: Optional[str] = "Administrator with full permissions",
    ) -> Role:
        """
        Create an admin role using templates
        """
        return await RoleCRUD.create_role_from_template(
            db=db,
            organization_id=organization_id,
            template_name="admin",
            role_name=role_name,
            description=description or "Administrator with full permissions",
        )

    @staticmethod
    async def create_manager_role(
        db: AsyncSession,
        organization_id: uuid.UUID,
        role_name: str = "Manager",
        description: Optional[str] = "Team manager with elevated project management permissions",
    ) -> Role:
        """
        Create a manager role for an organization.

        Args:
            db: Async database session
            organization_id: UUID of the organization
            role_name: Name of the role (default: "Manager")
            description: Role description (optional)

        Returns:
            Role: Created role object

        Raises:
            Exception: If database operation fails
        """
        return await RoleCRUD.create_role_from_template(
            db=db,
            organization_id=organization_id,
            template_name="manager",
            role_name=role_name,
            description=description or "Team manager with elevated project management permissions",
        )

    @staticmethod
    async def get_default_user_role(
        db: AsyncSession,
        organization_id: uuid.UUID,
        role_name: str = "Member",
        description: Optional[str] = "Organization Member with basic permissions",
    ) -> Role:
        """
        Get or create a default user role for an organization.
        """

        try:
            existing_role = await RoleCRUD.get_role_by_name_and_organization(
                db, role_name, organization_id
            )

            if existing_role:
                logger.info(
                    "Retrieved existing user role: id=%s, name=%s, organization_id=%s",
                    existing_role.id,
                    existing_role.name,
                    existing_role.organization_id,
                )
                return existing_role

            role = await RoleCRUD.create_role_from_template(
                db=db,
                organization_id=organization_id,
                template_name="member",
                role_name=role_name,
                description=description or "Organization member with basic permissions",
            )

            return role

        except Exception as e:
            logger.error(
                "Failed to get or create user role for organization_id=%s: %s",
                organization_id,
                str(e),
                exc_info=True,
            )
            raise Exception("Failed to get or create user role")

    @staticmethod
    async def get_role_by_name_and_organization(
        db: AsyncSession, role_name: str, organization_id: uuid.UUID
    ) -> Optional[Role]:
        """Get role by name and organization."""
        try:
            result = await db.execute(
                select(Role).where(Role.name == role_name, Role.organization_id == organization_id)
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(
                f"Error fetching role by name={role_name} for org={organization_id}: {str(e)}"
            )
            raise Exception("Failed to get role")
