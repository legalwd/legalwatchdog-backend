"""Async service for managing the Jurisdiction State (Compliance Ledger).

Provides async variants of the Ledger operations for use in FastAPI route handlers
and other async contexts (e.g. ChangeAcceptanceService).

The caller is responsible for committing/rolling back the transaction.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.modules.v1.jurisdictions.models.jurisdiction_state import (
    JurisdictionState,
    JurisdictionStateHistory,
)

logger = logging.getLogger("app")


class AsyncJurisdictionStateService:
    """Async service for managing jurisdiction state (Compliance Ledger).

    All methods are transaction-safe: they add objects to the session
    but never commit or rollback. The caller owns the transaction boundary.
    """

    def __init__(self, db: AsyncSession):
        """Initialize service with async database session.

        Args:
            db: Async database session.
        """
        self.db = db

    async def get_jurisdiction_state(self, jurisdiction_id: UUID) -> Dict[str, JurisdictionState]:
        """Retrieve the current accepted state for a jurisdiction.

        Args:
            jurisdiction_id: The jurisdiction UUID.

        Returns:
            Dict[str, JurisdictionState]: Map of field_key->JurisdictionState(by field_key).
        """
        stmt = (
            select(JurisdictionState)
            .where(JurisdictionState.jurisdiction_id == jurisdiction_id)
            .order_by(JurisdictionState.field_key)
        )
        result = await self.db.execute(stmt)
        states = result.scalars().all()
        return {s.field_key: s for s in states}

    async def get_history_for_state_ids(
        self, state_ids: List[UUID], limit: int = 500
    ) -> Dict[UUID, List[JurisdictionStateHistory]]:
        """Load history rows for the given state IDs, grouped by state_id (newest first per state).

        Used to attach audit history to each state item in get_jurisdiction_state responses.
        """
        if not state_ids:
            return {}
        stmt = (
            select(JurisdictionStateHistory)
            .where(JurisdictionStateHistory.state_id.in_(state_ids))
            .order_by(JurisdictionStateHistory.changed_at.desc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        rows = result.scalars().all()
        by_state: Dict[UUID, List[JurisdictionStateHistory]] = {}
        for h in rows:
            by_state.setdefault(h.state_id, []).append(h)
        return by_state

    async def get_jurisdiction_state_history_paginated(
        self, jurisdiction_id: UUID, limit: int, offset: int
    ) -> tuple[List[JurisdictionStateHistory], int]:
        """Paginated audit log of all jurisdiction state history for a jurisdiction.

        Returns (list of history rows, total count). Each row has state loaded for field_key.
        Uses a subquery so we get one result row per history record (no join collapsing).
        """
        state_ids_subq = select(JurisdictionState.id).where(
            JurisdictionState.jurisdiction_id == jurisdiction_id
        )
        count_stmt = (
            select(func.count())
            .select_from(JurisdictionStateHistory)
            .where(JurisdictionStateHistory.state_id.in_(state_ids_subq))
        )
        total_result = await self.db.execute(count_stmt)
        total = int(total_result.scalar() or 0)
        stmt = (
            select(JurisdictionStateHistory)
            .where(JurisdictionStateHistory.state_id.in_(state_ids_subq))
            .order_by(JurisdictionStateHistory.changed_at.desc())
            .options(selectinload(JurisdictionStateHistory.state))
            .limit(limit)
            .offset(offset)
        )
        result = await self.db.execute(stmt)
        history_rows = result.scalars().all()
        return list(history_rows), total

    async def update_or_create_field(
        self,
        jurisdiction_id: UUID,
        field_key: str,
        new_value: str,
        change_reason: str,
        user_id: Optional[UUID] = None,
        job_id: Optional[UUID] = None,
        source_evidence: Optional[List[str]] = None,
        existing_state: Optional[JurisdictionState] = None,
    ) -> JurisdictionState:
        """Update an existing Ledger field or create a new one.

        Does NOT commit. The caller must commit the session after
        all desired mutations are applied.

        Args:
            jurisdiction_id: The jurisdiction UUID.
            field_key: The field name in the Ledger.
            new_value: The new accepted value.
            change_reason: Audit trail description.
            user_id: User who triggered the update.
            job_id: Associated scrape job ID.
            source_evidence: List of source URLs backing this value.
            existing_state: Pre-fetched state to avoid extra query.

        Returns:
            JurisdictionState: The created or updated state object.

        Examples:
            >>> state = await svc.update_or_create_field(
            ...     jur_id, "min_wage", "$16/hr",
            ...     "Accepted Ticket #42", user_id=uid
            ... )
        """
        current_time = datetime.now(timezone.utc)
        evidence = source_evidence or []

        if existing_state:
            previous_value = existing_state.value

            if previous_value == new_value:
                return existing_state

            existing_state.value = new_value
            existing_state.confirmed_at = current_time
            existing_state.confirmed_by_user_id = user_id
            existing_state.source_evidence = evidence
            if job_id:
                existing_state.originating_job_id = job_id
            self.db.add(existing_state)

            history = JurisdictionStateHistory(
                state_id=existing_state.id,
                previous_value=previous_value,
                new_value=new_value,
                changed_at=current_time,
                changed_by_user_id=user_id,
                change_reason=change_reason,
            )
            self.db.add(history)
            return existing_state

        state = JurisdictionState(
            jurisdiction_id=jurisdiction_id,
            field_key=field_key,
            value=new_value,
            source_evidence=evidence,
            confirmed_at=current_time,
            confirmed_by_user_id=user_id,
            originating_job_id=job_id,
        )
        self.db.add(state)

        history = JurisdictionStateHistory(
            state=state,
            previous_value=None,
            new_value=new_value,
            changed_at=current_time,
            changed_by_user_id=user_id,
            change_reason=change_reason,
        )
        self.db.add(history)
        return state
