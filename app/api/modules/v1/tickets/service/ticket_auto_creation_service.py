from typing import TYPE_CHECKING, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.api.modules.v1.tickets.models.ticket_model import Ticket, TicketPriority, TicketStatus
from app.api.modules.v1.users.models.users_model import User

if TYPE_CHECKING:
    from app.api.modules.v1.jurisdictions.models.jurisdiction_model import Jurisdiction
    from app.api.modules.v1.projects.models.project_model import Project
    from app.api.modules.v1.scraping.models.data_revision import DataRevision
    from app.api.modules.v1.scraping.models.source_model import Source
    from app.api.modules.v1.scraping.service.diff_service import ChangeDetectionResult


class TicketService:
    """
    Service to handle creation of tickets automatically when
    a meaningful change is detected in a data revision.
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize the TicketService with a database session.
        """
        self.db = db

    @staticmethod
    def map_risk_to_priority(risk_level: Optional[str]) -> TicketPriority:
        """
        Maps the risk level detected by AI to the ticket priority.

        Args:
            risk_level (Optional[str]): Risk level string ("LOW", "MEDIUM", "HIGH", "CRITICAL").

        Returns:
            TicketPriority: The corresponding ticket priority.
        """
        risk_map = {
            "CRITICAL": TicketPriority.CRITICAL,
            "HIGH": TicketPriority.HIGH,
            "MEDIUM": TicketPriority.MEDIUM,
            "LOW": TicketPriority.LOW,
        }
        risk_upper = risk_level.upper() if risk_level else "LOW"
        return risk_map.get(risk_upper, TicketPriority.LOW)

    async def create_auto_ticket(
        self,
        revision: "DataRevision",
        source: "Source",
        jurisdiction: "Jurisdiction",
        project: "Project",
        change_result: "ChangeDetectionResult",
    ) -> Ticket:
        """
        Creates an automatic ticket for a data revision with a detected change.

        Args:
            revision (DataRevision): The revision object that triggered the ticket.
            source (Source): The source of the revision.
            jurisdiction (Jurisdiction): The jurisdiction the source belongs to.
            project (Project): The project the source belongs to.
            change_result (ChangeDetectionResult): The result from the DiffAIService.

        Returns:
            Ticket: The newly created ticket.
        """
        from app.api.modules.v1.scraping.models.change_diff import ChangeDiff

        query = select(User).where(User.is_active).limit(1)
        result = await self.db.execute(query)
        any_active_user: Optional[User] = result.scalars().first()
        created_by_user_id = any_active_user.id if any_active_user else None
        jurisdiction_name = jurisdiction.name if jurisdiction else "General"

        title = f"[{jurisdiction_name}] {source.name} - Change Detected"

        description = revision.ai_summary or "No summary available"

        change_diff_query = (
            select(ChangeDiff).where(ChangeDiff.new_revision_id == revision.id).limit(1)
        )
        change_diff_result = await self.db.execute(change_diff_query)
        change_diff = change_diff_result.scalar_one_or_none()

        content = {
            "revision_summary": revision.ai_summary,
            "source_name": source.name,
            "source_url": source.url,
            "jurisdiction": jurisdiction_name,
            "scraped_at": revision.scraped_at.isoformat() if revision.scraped_at else None,
            "content_hash": revision.content_hash,
            "diff_patch": {
                "risk_level": change_result.risk_level,
                "change_summary": change_result.change_summary,
            },
            "ai_confidence": revision.ai_confidence_score,
            "priority_inferred_from_ai": True,
        }

        if change_diff:
            content["change_diff_id"] = str(change_diff.diff_id)

        priority = self.map_risk_to_priority(change_result.risk_level)

        ticket = Ticket(
            title=title,
            description=description,
            content=content,
            status=TicketStatus.OPEN.value,
            priority=priority.value,
            is_manual=False,
            data_revision_id=revision.id,
            change_diff_id=change_diff.diff_id if change_diff else None,
            created_by_user_id=created_by_user_id,
            assigned_to_user_id=None,
            organization_id=project.org_id,
            project_id=project.id,
            source_id=source.id,
        )

        self.db.add(ticket)
        await self.db.flush()
        await self.db.refresh(ticket)

        return ticket
