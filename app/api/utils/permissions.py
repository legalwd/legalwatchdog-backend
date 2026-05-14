from enum import Enum


class Permission(str, Enum):
    """
    Granular permissions for RBAC system.
    Each permission controls access to specific operations.
    """

    # User Management
    MANAGE_USERS = "manage_users"
    INVITE_USERS = "invite_users"
    DEACTIVATE_USERS = "deactivate_users"
    ASSIGN_ROLES = "assign_roles"

    # Role Management
    CREATE_ROLES = "create_roles"
    EDIT_ROLES = "edit_roles"
    DELETE_ROLES = "delete_roles"
    VIEW_ROLES = "view_roles"

    # Organization Management
    MANAGE_ORGANIZATION = "manage_organization"
    CONFIGURE_SSO = "configure_sso"
    MANAGE_BILLING = "manage_billing"
    DELETE_ORGANIZATION = "delete_organization"

    # Project Management
    CREATE_PROJECTS = "create_projects"
    EDIT_PROJECTS = "edit_projects"
    DELETE_PROJECTS = "delete_projects"
    VIEW_PROJECTS = "view_projects"

    # Jurisdiction Management
    CREATE_JURISDICTIONS = "create_jurisdictions"
    EDIT_JURISDICTIONS = "edit_jurisdictions"
    DELETE_JURISDICTIONS = "delete_jurisdictions"
    VIEW_JURISDICTIONS = "view_jurisdictions"

    # Source Management
    CREATE_SOURCES = "create_sources"
    EDIT_SOURCES = "edit_sources"
    DELETE_SOURCES = "delete_sources"
    VIEW_SOURCES = "view_sources"
    TRIGGER_SCRAPING = "trigger_scraping"

    # Ticket Management
    CREATE_TICKETS = "create_tickets"
    EDIT_TICKETS = "edit_tickets"
    DELETE_TICKETS = "delete_tickets"
    VIEW_TICKETS = "view_tickets"
    ASSIGN_TICKETS = "assign_tickets"
    CLOSE_TICKETS = "close_tickets"

    # Participant Management
    INVITE_PARTICIPANTS = "invite_participants"
    REVOKE_PARTICIPANT_ACCESS = "revoke_participant_access"

    # Data & Revisions
    VIEW_REVISIONS = "view_revisions"
    EXPORT_DATA = "export_data"

    # API Access
    MANAGE_API_KEYS = "manage_api_keys"

    @classmethod
    def validate_permissions(cls, permissions: dict) -> bool:
        """Validate that all permission keys are valid enum values."""
        valid_permissions = {perm.value for perm in cls}
        return all(perm in valid_permissions for perm in permissions.keys())

    @classmethod
    def get_all_permission_values(cls) -> list:
        """Get all available permission values as strings."""
        return [perm.value for perm in cls]


class PermissionChecker:
    @staticmethod
    def has_permission(user_permissions: dict, permission: Permission) -> bool:
        return user_permissions.get(permission.value, False)

    @staticmethod
    def has_any_permission(user_permissions: dict, permissions: list) -> bool:
        return any(user_permissions.get(perm.value, False) for perm in permissions)
