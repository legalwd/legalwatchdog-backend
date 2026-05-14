"""Service for managing the Jurisdiction State (Compliance Ledger).

Handles the creation, retrieval, and updating of the 'Golden Record' for jurisdiction data.
Encapsulates all logic for maintaining the audit trail via JurisdictionStateHistory.

All mutation methods are transaction-safe: they add objects to the session
but never commit or rollback. The caller owns the transaction boundary.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlmodel import Session

from app.api.modules.v1.jurisdictions.models.jurisdiction_state import (
    JurisdictionState,
    JurisdictionStateHistory,
)

logger = logging.getLogger("app")


class JurisdictionStateService:
    """Service for managing jurisdiction state (Compliance Ledger).

    All mutation methods add objects to the session but do NOT commit.
    The caller is responsible for committing the transaction.
    """

    def __init__(self, db: Session):
        """Initialize service with database session.

        Args:
            db: Synchronous database session.
        """
        self.db = db

    def get_jurisdiction_state(self, jurisdiction_id: UUID) -> Dict[str, JurisdictionState]:
        """Retrieve the current accepted state for a jurisdiction.

        Args:
            jurisdiction_id: The jurisdiction UUID.

        Returns:
            Dict[str, JurisdictionState]: A map of field_key -> JurisdictionState.

        Examples:
            >>> svc = JurisdictionStateService(db)
            >>> state = svc.get_jurisdiction_state(jur_id)
            >>> print(state.keys())
        """
        stmt = select(JurisdictionState).where(JurisdictionState.jurisdiction_id == jurisdiction_id)
        result = self.db.execute(stmt)
        results = result.scalars().all()

        return {state.field_key: state for state in results}

    def initialize_state(
        self,
        jurisdiction_id: UUID,
        data: Dict[str, Any],
        originating_job_id: Optional[UUID] = None,
        user_id: Optional[UUID] = None,
    ) -> List[JurisdictionState]:
        """Initialize the state for a jurisdiction (Day 1).

        Does NOT commit. The caller must commit after this call.

        Args:
            jurisdiction_id: The jurisdiction UUID.
            data: Dictionary of field_key -> value (or dict with value/source info).
            originating_job_id: The scrape job triggering this initialization.
            user_id: The user confirming (None if auto-confirmed).

        Returns:
            List[JurisdictionState]: List of created state objects.

        Examples:
            >>> states = svc.initialize_state(jur_id, {"min_wage": "$15/hr"})
            >>> db.commit()
        """
        created_states = []
        current_time = datetime.now(timezone.utc)

        for field_key, field_data in data.items():
            value = field_data
            source_evidence: List[str] = []

            if isinstance(field_data, dict):
                if "canonical_value" in field_data:
                    value = field_data["canonical_value"]
                elif "value" in field_data:
                    value = field_data["value"]
                else:
                    value = str(field_data)

                if "sources" in field_data:
                    source_evidence = field_data["sources"]

            state = JurisdictionState(
                jurisdiction_id=jurisdiction_id,
                field_key=field_key,
                value=str(value),
                source_evidence=source_evidence,
                confirmed_at=current_time,
                confirmed_by_user_id=user_id,
                originating_job_id=originating_job_id,
            )
            self.db.add(state)
            created_states.append(state)

            history = JurisdictionStateHistory(
                state=state,
                previous_value=None,
                new_value=str(value),
                changed_at=current_time,
                changed_by_user_id=user_id,
                change_reason="Initial State Initialization",
            )
            self.db.add(history)

        logger.info(
            f"Prepared {len(created_states)} state fields for jurisdiction {jurisdiction_id}"
        )
        return created_states

    def update_state(
        self,
        jurisdiction_id: UUID,
        updates: Dict[str, Any],
        change_reason: str,
        user_id: Optional[UUID] = None,
        job_id: Optional[UUID] = None,
    ) -> List[JurisdictionState]:
        """Update specific fields in the jurisdiction state.

        Does NOT commit. The caller must commit after this call.

        Args:
            jurisdiction_id: The jurisdiction UUID.
            updates: Dict of field_key -> new_value.
            change_reason: Audit trail description.
            user_id: User performing the update.
            job_id: Optional job ID associated with the new value.

        Returns:
            List[JurisdictionState]: List of updated/created state objects.

        Examples:
            >>> updated = svc.update_state(
            ...     jur_id, {"min_wage": "$16/hr"},
            ...     "Accepted Ticket #42"
            ... )
            >>> db.commit()
        """
        updated_states = []
        current_time = datetime.now(timezone.utc)

        current_state_map = self.get_jurisdiction_state(jurisdiction_id)

        for field_key, new_val in updates.items():
            new_value_str = str(new_val)

            if field_key in current_state_map:
                state = current_state_map[field_key]

                if state.value == new_value_str:
                    continue

                previous_value = state.value

                state.value = new_value_str
                state.confirmed_at = current_time
                state.confirmed_by_user_id = user_id
                if job_id:
                    state.originating_job_id = job_id

                self.db.add(state)
                updated_states.append(state)

                history = JurisdictionStateHistory(
                    state_id=state.id,
                    previous_value=previous_value,
                    new_value=new_value_str,
                    changed_at=current_time,
                    changed_by_user_id=user_id,
                    change_reason=change_reason,
                )
                self.db.add(history)

            else:
                state = JurisdictionState(
                    jurisdiction_id=jurisdiction_id,
                    field_key=field_key,
                    value=new_value_str,
                    confirmed_at=current_time,
                    confirmed_by_user_id=user_id,
                    originating_job_id=job_id,
                )
                self.db.add(state)
                updated_states.append(state)

                history = JurisdictionStateHistory(
                    state=state,
                    previous_value=None,
                    new_value=new_value_str,
                    changed_at=current_time,
                    changed_by_user_id=user_id,
                    change_reason=change_reason,
                )
                self.db.add(history)

        return updated_states
