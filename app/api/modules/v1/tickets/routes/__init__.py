"""
Ticket routes exports
"""

from app.api.modules.v1.tickets.routes.comment_routes import router as comment_router
from app.api.modules.v1.tickets.routes.guest_access_routes import (
    router as guest_access_router,
)
from app.api.modules.v1.tickets.routes.participant_routes import (
    router as participant_router,
)
from app.api.modules.v1.tickets.routes.ticket_routes import router

__all__ = ["router", "participant_router", "guest_access_router", "comment_router"]
