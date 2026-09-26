"""
Notification Decision Engine — 10-step decision pipeline for personalized alert delivery
"""
import logging
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from apps.api.config import settings
from apps.api.models.user import User
from apps.api.models.opportunity import Opportunity
from apps.api.models.event import OpportunityEvent
from services.personalization.relevance_engine import PersonalizationEngine
from services.personalization.explanations import RelevanceResult
from services.notifications.priority import PriorityEscalator
from services.notifications.deduplication import NotificationDeduplicator
from services.notifications.throttling import NotificationThrottler
from shared.constants import DeliveryMode, PriorityLevel, EligibilityStatus

logger = logging.getLogger("signal.notifications.decision")


@dataclass
class NotificationDecision:
    """Structured decision produced by the decision engine."""
    should_notify: bool
    delivery_mode: DeliveryMode
    priority: PriorityLevel
    reason: str
    relevance_result: Optional[RelevanceResult] = None
    scheduled_for: Optional[datetime] = None

    def to_dict(self) -> dict:
        return {
            "should_notify": self.should_notify,
            "delivery_mode": self.delivery_mode.value,
            "priority": self.priority.value,
            "reason": self.reason,
            "relevance_result": self.relevance_result.to_dict() if self.relevance_result else None,
            "scheduled_for": self.scheduled_for.isoformat() if self.scheduled_for else None,
        }


class NotificationDecisionEngine:
    """
    Evaluates whether, when, and how an opportunity update should be delivered to a user.
    Enforces the complete 10-step anti-fatigue decision flow.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.personalization_engine = PersonalizationEngine(db)
        self.deduplicator = NotificationDeduplicator(db)
        self.throttler = NotificationThrottler(db)

    async def evaluate(
        self,
        user: User,
        opportunity: Opportunity,
        event: Optional[OpportunityEvent] = None,
    ) -> NotificationDecision:
        """
        Evaluate full notification decision pipeline for a user and opportunity.
        """
        # Ensure user relationships are eagerly loaded
        if user.id:
            from sqlalchemy.orm import selectinload
            user_stmt = (
                select(User)
                .where(User.id == user.id)
                .options(
                    selectinload(User.profile),
                    selectinload(User.preferences),
                    selectinload(User.interests),
                    selectinload(User.skills),
                )
            )
            loaded_user = (await self.db.execute(user_stmt)).scalars().first()
            if loaded_user:
                user = loaded_user

        # Step 1: User Active?
        if not user.is_active:
            return NotificationDecision(
                should_notify=False,
                delivery_mode=DeliveryMode.SKIPPED,
                priority=PriorityLevel.LOW,
                reason="User account is inactive",
            )

        # Step 2: Notifications Enabled?
        preferences = user.preferences
        if preferences and not preferences.enabled:
            return NotificationDecision(
                should_notify=False,
                delivery_mode=DeliveryMode.SKIPPED,
                priority=PriorityLevel.LOW,
                reason="Notifications disabled in user preferences",
            )

        min_relevance = preferences.min_relevance_score if preferences else settings.SIGNAL_DEFAULT_MIN_RELEVANCE_SCORE

        # Step 3: Evaluate Relevance
        relevance = await self.personalization_engine.evaluate_relevance(user, opportunity, event)

        # Step 4: Relevance Above Threshold?
        if relevance.score < min_relevance:
            return NotificationDecision(
                should_notify=False,
                delivery_mode=DeliveryMode.SKIPPED,
                priority=PriorityLevel.LOW,
                reason=f"Relevance score {relevance.score} is below user threshold ({min_relevance})",
                relevance_result=relevance,
            )

        # Step 5: Academic Eligibility Check
        if relevance.eligibility_status == EligibilityStatus.INELIGIBLE:
            return NotificationDecision(
                should_notify=False,
                delivery_mode=DeliveryMode.SKIPPED,
                priority=PriorityLevel.LOW,
                reason="User is not eligible for this opportunity",
                relevance_result=relevance,
            )

        # Step 6: Actionable Lifecycle Event Check
        event_type = event.event_type if event else opportunity.current_state
        if event and not self.deduplicator.is_actionable_event(event_type):
            return NotificationDecision(
                should_notify=False,
                delivery_mode=DeliveryMode.SKIPPED,
                priority=PriorityLevel.LOW,
                reason=f"Event type '{event_type}' is not actionable",
                relevance_result=relevance,
            )

        # Step 7: Deduplication & Cooldown Check
        event_id = event.id if event else None
        is_dup = await self.deduplicator.is_duplicate(user.id, opportunity.id, event_id)
        if is_dup:
            return NotificationDecision(
                should_notify=False,
                delivery_mode=DeliveryMode.SKIPPED,
                priority=PriorityLevel.LOW,
                reason="Notification already delivered or opportunity cooldown active",
                relevance_result=relevance,
            )

        # Step 8: Priority Escalation
        deadline_date = event.deadline_date if event else None
        is_watched = bool(relevance.matched_programs)
        escalated_priority = PriorityEscalator.escalate(
            base_priority=opportunity.priority,
            relevance_score=relevance.score,
            deadline_date=deadline_date,
            event_type=event_type,
            is_watched_program=is_watched,
        )

        # Step 9: Throttling & Quiet Hours Check
        quiet_hours_enabled = preferences.quiet_hours_enabled if preferences else False
        quiet_start = preferences.quiet_hours_start if preferences else "22:30"
        quiet_end = preferences.quiet_hours_end if preferences else "07:30"
        user_tz = preferences.timezone if preferences else (user.profile.timezone if user.profile else "Asia/Kolkata")
        max_daily = preferences.max_alerts_per_day if preferences else settings.SIGNAL_DEFAULT_DAILY_NOTIFICATION_LIMIT

        is_rate_limited, in_quiet_hours, throttle_reason = await self.throttler.evaluate_throttling(
            user_id=user.id,
            priority=escalated_priority,
            quiet_hours_enabled=quiet_hours_enabled,
            quiet_hours_start=quiet_start,
            quiet_hours_end=quiet_end,
            user_timezone=user_tz,
            max_alerts_per_day=max_daily,
        )

        if is_rate_limited:
            return NotificationDecision(
                should_notify=False,
                delivery_mode=DeliveryMode.SKIPPED,
                priority=escalated_priority,
                reason=throttle_reason,
                relevance_result=relevance,
            )

        # Step 10: Final Delivery Mode Decision
        if in_quiet_hours:
            # Queue for morning delivery when quiet hours end
            scheduled_for = datetime.now(timezone.utc) + timedelta(hours=8)
            return NotificationDecision(
                should_notify=True,
                delivery_mode=DeliveryMode.QUEUED,
                priority=escalated_priority,
                reason=f"Queued due to quiet hours: {throttle_reason}",
                relevance_result=relevance,
                scheduled_for=scheduled_for,
            )

        # Check digest preference
        if preferences and preferences.digest_enabled and not preferences.instant_alerts_enabled and escalated_priority != PriorityLevel.CRITICAL:
            return NotificationDecision(
                should_notify=True,
                delivery_mode=DeliveryMode.DIGEST,
                priority=escalated_priority,
                reason="Queued for daily digest as preferred by user",
                relevance_result=relevance,
            )

        # Default: Instant delivery
        return NotificationDecision(
            should_notify=True,
            delivery_mode=DeliveryMode.INSTANT,
            priority=escalated_priority,
            reason=f"Approved for immediate delivery ({escalated_priority.value.upper()} priority, score {relevance.score})",
            relevance_result=relevance,
        )

    # Backward compatibility alias
    evaluate_notification_decision = evaluate
