class RoleHierarchyException(Exception):
    """Base exception for role hierarchy violations."""

    def __init__(self, message: str, status_code: int = 403):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class InsufficientRoleException(RoleHierarchyException):
    """Raised when user's role is insufficient to perform an action."""

    def __init__(self, message: str):
        super().__init__(message, status_code=403)


class CannotManageHigherRoleException(RoleHierarchyException):
    """Raised when attempting to manage a user with equal or higher role."""

    def __init__(self, user_role: str, target_role: str, action: str = "manage"):
        message = (
            f"You cannot {action} a {target_role}. "
            f"Only higher-level roles can {action} {target_role}s."
        )
        super().__init__(message, status_code=403)


class CannotAssignRoleException(RoleHierarchyException):
    """Raised when attempting to assign a role above your level."""

    def __init__(self, user_role: str, target_role_name: str):
        message = (
            f"You cannot assign the {target_role_name} role. "
            f"Your role ({user_role}) can only assign roles below your level."
        )
        super().__init__(message, status_code=403)


class MembershipNotFoundException(Exception):
    """Raised when user membership is not found."""

    def __init__(self, message: str = "User is not a member of this organization"):
        self.message = message
        self.status_code = 404
        super().__init__(self.message)


class RoleNotFoundException(Exception):
    """Raised when a role is not found."""

    def __init__(self, message: str = "Role not found"):
        self.message = message
        self.status_code = 404
        super().__init__(self.message)


class SelfManagementException(RoleHierarchyException):
    """Raised when user attempts to manage their own account through restricted endpoints."""

    def __init__(self, action: str = "manage"):
        message = f"You cannot {action} your own account through this endpoint"
        super().__init__(message, status_code=403)
