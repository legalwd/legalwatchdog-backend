"""
Guest Access Token Utilities for External Participants

These tokens are DIFFERENT from regular user JWT tokens:
- They have aud="guest_access" to prevent use on regular API endpoints
- They contain ticket_id to scope access to ONE specific ticket
- They expire (default 7 days)
- They can be revoked via token_hash
"""

import hashlib
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

import jwt
from pydantic import BaseModel

from app.api.core.config import settings

logger = logging.getLogger("app")


class GuestTokenPayload(BaseModel):
    """Payload structure for guest access tokens"""

    sub: str
    ticket_id: str
    aud: str = "guest_access"
    exp: int


def create_guest_token(
    participant_id: UUID,
    ticket_id: UUID,
    expiry_days: int = 7,
) -> str:
    """
    Create a secure JWT token for external participant guest access.

    This token allows access to ONE specific ticket without requiring login.

    Args:
        participant_id: UUID of the ExternalParticipant record
        ticket_id: UUID of the ticket they can access
        expiry_days: Number of days until token expires (default: 7)

    Returns:
        JWT token string

    Example:
        token = create_guest_token(
            participant_id=UUID("..."),
            ticket_id=UUID("..."),
            expiry_days=7
        )
        # Returns: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
    """
    expiration = datetime.now(timezone.utc) + timedelta(days=expiry_days)

    payload = {
        "sub": str(participant_id),
        "ticket_id": str(ticket_id),
        "aud": "guest_access",
        "exp": int(expiration.timestamp()),
        "iat": int(datetime.now(timezone.utc).timestamp()),
    }

    token = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")

    logger.info(
        f"Created guest access token for participant {participant_id} "
        f"on ticket {ticket_id} (expires in {expiry_days} days)"
    )

    return token


def decode_guest_token(token: str) -> Optional[GuestTokenPayload]:
    """
    Decode and validate a guest access token.

    Args:
        token: JWT token string

    Returns:
        GuestTokenPayload if valid, None if invalid

    Validates:
        - Token signature
        - Token expiration
        - Audience is "guest_access"
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=["HS256"],
            audience="guest_access",
        )

        return GuestTokenPayload(**payload)

    except jwt.ExpiredSignatureError:
        logger.warning("Guest token expired")
        return None
    except jwt.InvalidAudienceError:
        logger.warning("Invalid token audience (not guest_access)")
        return None
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid guest token: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Error decoding guest token: {str(e)}", exc_info=True)
        return None


def hash_token(token: str) -> str:
    """
    Create a SHA256 hash of the token for revocation purposes.

    We store hashes (not raw tokens) in the database so we can:
    1. Revoke specific tokens if needed
    2. Avoid storing sensitive token data

    Args:
        token: JWT token string

    Returns:
        SHA256 hash of the token
    """
    return hashlib.sha256(token.encode()).hexdigest()


def verify_token_for_ticket(token: str, ticket_id: UUID) -> bool:
    """
    Verify that a guest token is valid for a specific ticket.

    This is CRITICAL for security - ensures the token can ONLY access
    the ticket it was issued for.

    Args:
        token: JWT token string
        ticket_id: UUID of the ticket being accessed

    Returns:
        True if token is valid for this ticket, False otherwise
    """
    payload = decode_guest_token(token)

    if not payload:
        return False

    if payload.ticket_id != str(ticket_id):
        logger.warning(
            f"Token ticket mismatch: token for {payload.ticket_id}, "
            f"but trying to access {ticket_id}"
        )
        return False

    return True
