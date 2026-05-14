"""
Comment authentication and authorization dependency.

Provides unified authentication for comments that works with both:
- Regular users (JWT with user context)
- Guest participants (JWT with guest/participant context)
"""

from typing import Optional, Union
from uuid import UUID

from fastapi import Depends

from app.api.core.dependencies.guest_auth import GuestContext, get_user_or_guest
from app.api.modules.v1.users.models.users_model import User


class CommentAuthor:
    """
    Unified author context for comments.

    Can be either a regular user or an external participant (guest).
    Routes use this to identify who's creating/updating/deleting comments.
    """

    def __init__(
        self,
        user: Optional[User] = None,
        guest: Optional[GuestContext] = None,
    ):
        self.user = user
        self.guest = guest

    @property
    def user_id(self) -> Optional[UUID]:
        """Get user ID if this is a regular user, None otherwise."""
        return self.user.id if self.user else None

    @property
    def participant_id(self) -> Optional[UUID]:
        """Get participant ID if this is a guest, None otherwise."""
        return self.guest.participant_id if self.guest else None

    @property
    def is_guest(self) -> bool:
        """True if this is a guest participant, False if regular user."""
        return self.guest is not None

    def __str__(self) -> str:
        """String representation for logging."""
        if self.user:
            return f"User({self.user.email})"
        elif self.guest:
            return f"Guest({self.guest.email})"
        return "Unknown"


async def get_comment_author(
    user_or_guest: Union[User, GuestContext] = Depends(get_user_or_guest),
) -> CommentAuthor:
    """
    Dependency to get the authenticated author of a comment.

    Uses get_user_or_guest which properly handles both:
    - Regular user JWT tokens
    - Guest JWT tokens

    Returns:
        CommentAuthor with either user_id or participant_id set
    """
    if isinstance(user_or_guest, GuestContext):
        return CommentAuthor(guest=user_or_guest)
    else:
        return CommentAuthor(user=user_or_guest)
