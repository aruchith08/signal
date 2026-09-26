"""Opportunity Structured Change Detection Service (Phase 5A)

Detects field-level differences between an existing Opportunity record and
newly incoming normalized data, recording meaningful changes as ChangeSet rows.

Duplicate ChangeSet rows (same opportunity, field, previous, and new values)
are prevented so re-ingesting identical data creates zero ChangeSet records.
Brand-new opportunities do not create ChangeSets (initial creation is not a change).
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.models.change_set import ChangeSet
from apps.api.models.opportunity import Opportunity
from apps.api.models.verification import VerifiedField
from shared.constants import ChangeType, EventType, PriorityLevel

logger = logging.getLogger("signal.ingestion.opportunity_change_detection")

# Monitored field definitions: (ChangeType, PriorityLevel)
_FIELD_METADATA = {
    "deadline_date": (ChangeType.DEADLINE_CHANGED, PriorityLevel.CRITICAL),
    "current_state": (ChangeType.STATUS_CHANGED, PriorityLevel.HIGH),
    "status": (ChangeType.STATUS_CHANGED, PriorityLevel.HIGH),
    "eligibility": (ChangeType.CONTENT_CHANGED, PriorityLevel.MEDIUM),
    "application_url": (ChangeType.CONTENT_CHANGED, PriorityLevel.MEDIUM),
    "title": (ChangeType.CONTENT_CHANGED, PriorityLevel.LOW),
    "season": (ChangeType.CONTENT_CHANGED, PriorityLevel.LOW),
    "year": (ChangeType.CONTENT_CHANGED, PriorityLevel.LOW),
}


class OpportunityChangeDetector:
    """Detects and records field-level changes for an Opportunity."""

    def _determine_change_type_and_importance(
        self, field_name: str, old_val: Optional[str], new_val: Optional[str]
    ) -> tuple[ChangeType, PriorityLevel]:
        """Map changed field and values to domain ChangeType and PriorityLevel."""
        if field_name == "deadline_date":
            return ChangeType.DEADLINE_CHANGED, PriorityLevel.CRITICAL

        if field_name in ("current_state", "status"):
            critical_states = {
                EventType.DEADLINE_CHANGED.value,
                EventType.DEADLINE_EXTENDED.value,
                EventType.DEADLINE_SHORTENED.value,
                EventType.REGISTRATION_CLOSING.value,
                EventType.APPLICATION_DEADLINE.value,
            }
            if new_val in critical_states:
                return ChangeType.DEADLINE_CHANGED, PriorityLevel.CRITICAL
            return ChangeType.STATUS_CHANGED, PriorityLevel.HIGH

        default_ct, default_prio = _FIELD_METADATA.get(
            field_name, (ChangeType.CONTENT_CHANGED, PriorityLevel.MEDIUM)
        )
        return default_ct, default_prio

    async def _get_existing_deadline(
        self, session: AsyncSession, opp_id: str
    ) -> Optional[str]:
        """Retrieve existing verified deadline or latest detected deadline ChangeSet."""
        # 1. Check VerifiedField
        stmt = (
            select(VerifiedField.value)
            .where(
                VerifiedField.opportunity_id == opp_id,
                VerifiedField.field_name == "deadline",
            )
            .limit(1)
        )
        val = (await session.execute(stmt)).scalar_one_or_none()
        if val:
            return val

        # 2. Check OpportunityEvent
        from apps.api.models.event import OpportunityEvent
        event_stmt = (
            select(OpportunityEvent.deadline_date)
            .where(
                OpportunityEvent.opportunity_id == opp_id,
                OpportunityEvent.deadline_date.isnot(None),
            )
            .order_by(OpportunityEvent.created_at.desc())
            .limit(1)
        )
        event_val = (await session.execute(event_stmt)).scalar_one_or_none()
        if event_val:
            return str(event_val)

        # 3. Check uncommitted ChangeSet in current session
        for obj in reversed(list(session.new)):
            if (
                isinstance(obj, ChangeSet)
                and obj.opportunity_id == opp_id
                and obj.field_name == "deadline_date"
            ):
                if obj.new_value:
                    return obj.new_value

        # 3. Check persisted ChangeSets
        cs_stmt = (
            select(ChangeSet.new_value)
            .where(
                ChangeSet.opportunity_id == opp_id,
                ChangeSet.field_name == "deadline_date",
            )
            .order_by(ChangeSet.detected_at.desc(), ChangeSet.created_at.desc())
            .limit(1)
        )
        return (await session.execute(cs_stmt)).scalar_one_or_none()

    async def _is_duplicate_changeset(
        self,
        session: AsyncSession,
        opp_id: str,
        field_name: str,
        prev_str: Optional[str],
        new_str: Optional[str],
    ) -> bool:
        """Check if an identical ChangeSet already exists in the session or database."""
        # Check pending uncommitted additions in current session
        for obj in session.new:
            if isinstance(obj, ChangeSet):
                if (
                    obj.opportunity_id == opp_id
                    and obj.field_name == field_name
                    and obj.previous_value == prev_str
                    and obj.new_value == new_str
                ):
                    return True

        # Check database
        stmt = (
            select(ChangeSet)
            .where(
                ChangeSet.opportunity_id == opp_id,
                ChangeSet.field_name == field_name,
                ChangeSet.previous_value == prev_str,
                ChangeSet.new_value == new_str,
            )
            .limit(1)
        )
        existing = (await session.execute(stmt)).scalars().first()
        return existing is not None

    async def detect_and_record(
        self,
        session: AsyncSession,
        existing_opp: Optional[Opportunity],
        incoming_data: Dict[str, Any],
        source_snapshot_id: Optional[str] = None,
    ) -> List[ChangeSet]:
        """
        Compare existing Opportunity attributes with incoming normalized data
        BEFORE values are overwritten.

        Returns a list of created ChangeSet records (empty if no changes or duplicates).
        Initial opportunity creation creates 0 ChangeSets.
        """
        # Initial creation is NOT a change
        if existing_opp is None or not getattr(existing_opp, "id", None):
            return []

        created_changesets: List[ChangeSet] = []

        for field_name in _FIELD_METADATA:
            if field_name not in incoming_data:
                continue

            new_raw = incoming_data.get(field_name)
            if new_raw is None:
                continue

            new_str = str(new_raw).strip()

            # Retrieve old value
            if field_name == "deadline_date":
                old_raw = getattr(existing_opp, "deadline_date", None)
                if old_raw is None:
                    old_raw = await self._get_existing_deadline(session, existing_opp.id)
            else:
                old_raw = getattr(existing_opp, field_name, None)

            old_str = str(old_raw).strip() if old_raw is not None else None

            # 1. Natural Comparison: No Change
            if old_str == new_str or (not old_str and not new_str):
                continue

            # 2. Duplicate Check
            if await self._is_duplicate_changeset(
                session, existing_opp.id, field_name, old_str, new_str
            ):
                logger.debug(
                    f"[ChangeDetector] Skipping duplicate ChangeSet for {existing_opp.id} field {field_name}"
                )
                continue

            change_type, importance = self._determine_change_type_and_importance(
                field_name, old_str, new_str
            )

            cs = ChangeSet(
                opportunity_id=existing_opp.id,
                source_discovery_id=source_snapshot_id,
                field_name=field_name,
                previous_value=old_str,
                new_value=new_str,
                change_type=change_type.value,
                importance=importance.value,
                detected_at=datetime.now(timezone.utc),
                resolved=False,
            )
            session.add(cs)
            created_changesets.append(cs)
            logger.info(
                f"[ChangeDetector] Recorded ChangeSet for Opp {existing_opp.id}: "
                f"{field_name} changed from '{old_str}' to '{new_str}' (type={change_type.value}, imp={importance.value})"
            )

        return created_changesets
