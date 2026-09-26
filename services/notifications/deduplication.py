"""
Notification Deduplication & Meaningful Event Gate
"""
from datetime import datetime, timezone, timedelta
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from apps.api.models.notification import Notification
from shared.constants import NotificationStatus, EventType


class NotificationDeduplicator:
    """
    Enforces strict anti-spam notification deduplication.
    Guarantees:
    - Never delivers repeated notifications for the same (user, opportunity, event) tuple.
    - Enforces an opportunity cooldown window for non-critical repeated updates.
    """

    ACTIONABLE_EVENTS = {
        EventType.ANNOUNCEMENT.value,
        EventType.ANNOUNCED.value,
        EventType.REGISTRATION_OPEN.value,
        EventType.REGISTRATION_CLOSING.value,
        EventType.APPLICATION_OPEN.value,
        EventType.APPLICATION_CLOSING.value,
        EventType.APPLICATION_DEADLINE.value,
        EventType.DEADLINE_CHANGED.value,
        EventType.DEADLINE_EXTENDED.value,
        EventType.DEADLINE_SHORTENED.value,
        EventType.DEADLINE_ANNOUNCED.value,
        EventType.RESULTS_RELEASED.value,
        EventType.RESULTS_ANNOUNCED.value,
        EventType.WINNERS_ANNOUNCED.value,
    }

    def __init__(self, db: AsyncSession):
        self.db = db

    @classmethod
    def is_actionable_event(cls, event_type: Optional[str]) -> bool:
        """Verify if event type represents a user-actionable lifecycle state."""
        if not event_type:
            return True
        return event_type.lower() in cls.ACTIONABLE_EVENTS

    async def is_duplicate(
        self,
        user_id: str,
        opportunity_id: str,
        event_id: Optional[str] = None,
        cooldown_hours: int = 12,
    ) -> bool:
        """
        Check if user has already been notified about this event or opportunity recently.
        """
        # 1. Exact Event Duplicate Check
        if event_id:
            stmt = select(Notification).where(
                Notification.user_id == user_id,
                Notification.opportunity_id == opportunity_id,
                Notification.event_id == event_id,
                Notification.status.in_([
                    NotificationStatus.SENT.value,
                    NotificationStatus.DELIVERED.value,
                    NotificationStatus.PENDING.value,
                    NotificationStatus.QUEUED.value,
                ]),
            )
            existing = (await self.db.execute(stmt)).scalars().first()
            if existing:
                return True

        # 2. Opportunity Cooldown Window Check (prevent spamming same opp multiple times within cooldown)
        cutoff = datetime.now(timezone.utc) - timedelta(hours=cooldown_hours)
        from sqlalchemy import or_
        cooldown_stmt = select(Notification).where(
            Notification.user_id == user_id,
            Notification.opportunity_id == opportunity_id,
            Notification.status.in_([
                NotificationStatus.SENT.value,
                NotificationStatus.DELIVERED.value,
                NotificationStatus.QUEUED.value,
                NotificationStatus.PENDING.value,
            ]),
            or_(
                Notification.sent_at >= cutoff,
                Notification.created_at >= cutoff,
            ),
        )
        recent_notification = (await self.db.execute(cooldown_stmt)).scalars().first()
        if recent_notification:
            return True

        return False
