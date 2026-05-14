import logging
from typing import Union
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.core.dependencies.auth import get_current_user
from app.api.core.dependencies.guest_auth import GuestContext, get_user_or_guest
from app.api.db.database import get_db
from app.api.modules.v1.tickets.schemas import (
    TicketCreate,
    TicketResponse,
)
from app.api.modules.v1.tickets.service import TicketService
from app.api.modules.v1.users.models.users_model import User
from app.api.utils.pagination import calculate_pagination
from app.api.utils.response_payloads import success_response

from .docs.ticket_routes_docs import (
    create_manual_ticket_custom_errors,
    create_manual_ticket_custom_success,
    create_manual_ticket_request_body,
    create_manual_ticket_responses,
    get_ticket_by_id_custom_errors,
    get_ticket_by_id_custom_success,
    get_ticket_by_id_responses,
    get_tickets_by_source_custom_errors,
    get_tickets_by_source_custom_success,
    get_tickets_by_source_responses,
)

logger = logging.getLogger("app")

router = APIRouter(
    prefix="/tickets",
    tags=["Tickets"],
)


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=TicketResponse,
    responses=create_manual_ticket_responses,
)
async def create_manual_ticket(
    data: TicketCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a new manual ticket.

    This endpoint allows authorized users to manually create tickets for revisions or observations
    that require discussion or follow-up.

    **Access Control:**
    - Only users with CREATE_TICKETS permission (admins/managers/owners) can create tickets
    - Regular project members cannot create tickets

    **Ticket Types:**

    1. **Source-Level Tickets**: For specific source revisions
       - Required: `source_id` + `revision_id`
       - Optional: `priority`

    2. **Jurisdiction-Level Tickets**: For consolidated jurisdiction changes
       - Required: `jurisdiction_id` + `jurisdiction_scrape_job_id`
       - Optional: `priority`

    **Returns:**
    - Created ticket with full details
    """
    ticket_service = TicketService(db)
    ticket = await ticket_service.create_manual_ticket(
        data=data,
        user_id=current_user.id,
    )

    logger.info(f"Successfully created ticket {ticket.id} for user {current_user.id}")

    return success_response(
        data={"ticket": ticket},
        message="Ticket created successfully",
        status_code=status.HTTP_201_CREATED,
    )


create_manual_ticket._custom_errors = create_manual_ticket_custom_errors
create_manual_ticket._custom_success = create_manual_ticket_custom_success
create_manual_ticket._request_body = create_manual_ticket_request_body


@router.get(
    "",
    status_code=status.HTTP_200_OK,
    responses=get_tickets_by_source_responses,
)
async def get_tickets(
    source_id: UUID = None,
    jurisdiction_id: UUID = None,
    organization_id: UUID = None,
    page: int = 1,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get paginated tickets with optional filters.

    Retrieves tickets with optional filtering by source, jurisdiction, or organization.
    At least one filter parameter must be provided.

    **Query Parameters:**
    - **source_id** (optional): Filter by Source UUID - returns tickets from that specific source
    - **jurisdiction_id** (optional): - returns tickets from ALL sources in that jurisdiction
    - **organization_id** (optional): - returns tickets across projects in that organization
    - **page** (optional): Page number (default: 1)
    - **limit** (optional): Items per page (default: 20, max: 100)

    **Returns:**
    - Paginated list of tickets matching the filters, ordered by creation date (newest first)

    **Filter Behavior:**
    - **source_id**: Returns all tickets from that specific source
    - **jurisdiction_id**: Returns all tickets from all sources within that jurisdiction
    - **organization_id**:
        - For admins/managers/owners (VIEW_TICKETS): Returns all tickets in the organization
        - For regular members: Returns tickets only from projects they're members of in that org
    - **Multiple filters**: When multiple filters are provided, (tickets must match ALL criteria)

    **Access Control:**
    - Users with VIEW_TICKETS permission (admins/managers/owners):
        - Can view all tickets in their organization based on filters provided
    - Project members (without VIEW_TICKETS):
        - Can only view tickets from projects they're members of
        - organization_id filter automatically scopes to their projects
        - jurisdiction_id and source_id require membership in the respective project
    - Others → Permission Denied

    **Examples:**
    - `/tickets?source_id=<uuid>` - Tickets from specific source
    - `/tickets?jurisdiction_id=<uuid>` - All tickets in jurisdiction
    - `/tickets?organization_id=<uuid>` - All tickets in org (scoped by permission)
    - `/tickets?source_id=<uuid>&organization_id=<uuid>` - Combined filter (AND logic)

    **Notes:**
    - At least one of source_id, jurisdiction_id, or organization_id must be provided
    - Hierarchy: Organization → Project(s) → Jurisdiction(s) → Source(s) → Ticket(s)
    """

    ticket_service = TicketService(db)
    tickets, total = await ticket_service.get_tickets(
        source_id=source_id,
        jurisdiction_id=jurisdiction_id,
        organization_id=organization_id,
        user_id=current_user.id,
        page=page,
        limit=limit,
    )

    pagination = calculate_pagination(total, page, limit)

    filters_applied = []
    if source_id:
        filters_applied.append(f"source={source_id}")
    if jurisdiction_id:
        filters_applied.append(f"jurisdiction={jurisdiction_id}")
    if organization_id:
        filters_applied.append(f"organization={organization_id}")

    logger.info(
        f"Successfully retrieved {len(tickets)} tickets (page {page}/{pagination['total_pages']}) "
        f"with filters: {', '.join(filters_applied)}, user_id={current_user.id}"
    )

    return success_response(
        data={
            "tickets": tickets,
            "pagination": pagination,
        },
        message=f"Retrieved {len(tickets)} ticket(s)",
        status_code=status.HTTP_200_OK,
    )


get_tickets._custom_errors = get_tickets_by_source_custom_errors
get_tickets._custom_success = get_tickets_by_source_custom_success


@router.get(
    "/{ticket_id}",
    status_code=status.HTTP_200_OK,
    responses=get_ticket_by_id_responses,
)
async def get_ticket_by_id(
    ticket_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_or_guest: Union[User, GuestContext] = Depends(get_user_or_guest),
):
    """
    Get a single ticket by ID with comments.

    Retrieves detailed information about a specific ticket including metadata, relationships,
    and discussion comments.

    **Path Parameters:**
    - **ticket_id** (required): Ticket UUID

    **Returns:**
    - Complete ticket details including:
      - Basic info: ID, title, description, status, priority
      - Relationships: creator, assignee, assigned by user, invited participants
      - Comments: Latest up to 20 comments ordered by creation date (newest first)
        - Each comment includes: author details, content, attachments, timestamps
        - Comments can have image attachments with metadata

    **Comments Section:**
    - Returns the **last 20 comments** (newest first)
    - Each comment includes:
      - author info (user or guest)
      - text content
      - image attachments (with URLs, file info, metadata)
      - creation and update timestamps
    - For pagination or to fetch additional comments, use the separate comments endpoint

    **Access Control:**
    - Users with VIEW_TICKETS permission (admins/managers/owners) can view all tickets
    - Project members can view tickets from their projects
    - Internal participants can view their ticket
    - External participants (guests) can view their ticket
    - Others → Permission Denied

    **Errors:**
    - 401: Authentication required
    - 403: Access denied (not in project/participants/permission)
    - 404: Ticket not found
    - 422: Invalid ticket_id format
    - 500: Server error
    """
    ticket_service = TicketService(db)
    ticket_data = await ticket_service.get_ticket_by_id(
        ticket_id=ticket_id,
        user_or_guest=user_or_guest,
    )

    logger.info(f"Retrieved ticket {ticket_id}")

    return success_response(
        data={"ticket": ticket_data},
        message="Ticket retrieved successfully",
        status_code=status.HTTP_200_OK,
    )


get_ticket_by_id._custom_errors = get_ticket_by_id_custom_errors
get_ticket_by_id._custom_success = get_ticket_by_id_custom_success
