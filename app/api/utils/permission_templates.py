from app.api.utils.permissions import Permission

OWNER_PERMISSIONS = {
    Permission.MANAGE_USERS.value: True,
    Permission.INVITE_USERS.value: True,
    Permission.DEACTIVATE_USERS.value: True,
    Permission.ASSIGN_ROLES.value: True,
    Permission.CREATE_ROLES.value: True,
    Permission.EDIT_ROLES.value: True,
    Permission.DELETE_ROLES.value: True,
    Permission.VIEW_ROLES.value: True,
    Permission.MANAGE_ORGANIZATION.value: True,
    Permission.DELETE_ORGANIZATION.value: True,
    Permission.CONFIGURE_SSO.value: True,
    Permission.MANAGE_BILLING.value: True,
    Permission.CREATE_PROJECTS.value: True,
    Permission.EDIT_PROJECTS.value: True,
    Permission.DELETE_PROJECTS.value: True,
    Permission.VIEW_PROJECTS.value: True,
    Permission.CREATE_JURISDICTIONS.value: True,
    Permission.EDIT_JURISDICTIONS.value: True,
    Permission.DELETE_JURISDICTIONS.value: True,
    Permission.VIEW_JURISDICTIONS.value: True,
    Permission.CREATE_SOURCES.value: True,
    Permission.EDIT_SOURCES.value: True,
    Permission.DELETE_SOURCES.value: True,
    Permission.VIEW_SOURCES.value: True,
    Permission.TRIGGER_SCRAPING.value: True,
    Permission.CREATE_TICKETS.value: True,
    Permission.EDIT_TICKETS.value: True,
    Permission.DELETE_TICKETS.value: True,
    Permission.VIEW_TICKETS.value: True,
    Permission.ASSIGN_TICKETS.value: True,
    Permission.CLOSE_TICKETS.value: True,
    Permission.INVITE_PARTICIPANTS.value: True,
    Permission.REVOKE_PARTICIPANT_ACCESS.value: True,
    Permission.VIEW_REVISIONS.value: True,
    Permission.EXPORT_DATA.value: True,
    Permission.MANAGE_API_KEYS.value: True,
}

ADMIN_PERMISSIONS = {
    Permission.MANAGE_USERS.value: True,
    Permission.INVITE_USERS.value: True,
    Permission.DEACTIVATE_USERS.value: True,
    Permission.ASSIGN_ROLES.value: True,
    Permission.CREATE_ROLES.value: True,
    Permission.EDIT_ROLES.value: True,
    Permission.DELETE_ROLES.value: True,
    Permission.VIEW_ROLES.value: True,
    Permission.MANAGE_ORGANIZATION.value: True,
    Permission.CONFIGURE_SSO.value: True,
    Permission.MANAGE_BILLING.value: True,
    Permission.CREATE_PROJECTS.value: True,
    Permission.EDIT_PROJECTS.value: True,
    Permission.DELETE_PROJECTS.value: True,
    Permission.VIEW_PROJECTS.value: True,
    Permission.CREATE_JURISDICTIONS.value: True,
    Permission.EDIT_JURISDICTIONS.value: True,
    Permission.DELETE_JURISDICTIONS.value: True,
    Permission.VIEW_JURISDICTIONS.value: True,
    Permission.CREATE_SOURCES.value: True,
    Permission.EDIT_SOURCES.value: True,
    Permission.DELETE_SOURCES.value: True,
    Permission.VIEW_SOURCES.value: True,
    Permission.TRIGGER_SCRAPING.value: True,
    Permission.CREATE_TICKETS.value: True,
    Permission.EDIT_TICKETS.value: True,
    Permission.DELETE_TICKETS.value: True,
    Permission.VIEW_TICKETS.value: True,
    Permission.ASSIGN_TICKETS.value: True,
    Permission.CLOSE_TICKETS.value: True,
    Permission.INVITE_PARTICIPANTS.value: True,
    Permission.REVOKE_PARTICIPANT_ACCESS.value: True,
    Permission.VIEW_REVISIONS.value: True,
    Permission.EXPORT_DATA.value: True,
    Permission.MANAGE_API_KEYS.value: True,
}

MANAGER_PERMISSIONS = {
    Permission.INVITE_USERS.value: True,
    Permission.VIEW_ROLES.value: True,
    Permission.CREATE_PROJECTS.value: True,
    Permission.EDIT_PROJECTS.value: True,
    Permission.VIEW_PROJECTS.value: True,
    Permission.CREATE_JURISDICTIONS.value: True,
    Permission.EDIT_JURISDICTIONS.value: True,
    Permission.VIEW_JURISDICTIONS.value: True,
    Permission.CREATE_SOURCES.value: True,
    Permission.EDIT_SOURCES.value: True,
    Permission.VIEW_SOURCES.value: True,
    Permission.TRIGGER_SCRAPING.value: True,
    Permission.CREATE_TICKETS.value: True,
    Permission.EDIT_TICKETS.value: True,
    Permission.VIEW_TICKETS.value: True,
    Permission.ASSIGN_TICKETS.value: True,
    Permission.CLOSE_TICKETS.value: True,
    Permission.INVITE_PARTICIPANTS.value: True,
    Permission.VIEW_REVISIONS.value: True,
    Permission.EXPORT_DATA.value: True,
}


USER_PERMISSIONS = {
    Permission.VIEW_PROJECTS.value: True,
    Permission.VIEW_JURISDICTIONS.value: True,
    Permission.VIEW_SOURCES.value: True,
    Permission.VIEW_REVISIONS.value: True,
}


class HardcodedRoleTemplates:
    """Temporary hardcoded role templates."""

    TEMPLATES = {
        "owner": {
            "name": "Owner",
            "description": "Organization owner with full permissions",
            "hierarchy_level": 4,
            "is_system_role": True,
            "permissions": OWNER_PERMISSIONS,
        },
        "admin": {
            "name": "Admin",
            "description": "Administrator with full permissions",
            "hierarchy_level": 3,
            "is_system_role": True,
            "permissions": ADMIN_PERMISSIONS,
        },
        "manager": {
            "name": "Manager",
            "description": "Team manager with elevated project management permissions",
            "hierarchy_level": 2,
            "is_system_role": True,
            "permissions": MANAGER_PERMISSIONS,
        },
        "member": {
            "name": "Member",
            "description": "Organization member with basic permissions",
            "hierarchy_level": 1,
            "is_system_role": True,
            "permissions": USER_PERMISSIONS,
        },
    }

    @classmethod
    def get_template(cls, template_name: str) -> dict:
        """Get template by name."""
        return cls.TEMPLATES.get(template_name.lower(), {}).copy()

    @classmethod
    def get_available_templates(cls) -> list:
        """Get list of available template names."""
        return list(cls.TEMPLATES.keys())
