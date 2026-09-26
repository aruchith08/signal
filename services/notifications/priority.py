"""
Priority Escalation and Urgency Evaluator
"""
from datetime import datetime, timezone
from typing import Optional
from shared.constants import PriorityLevel, UrgencyLevel, EventType


class PriorityEscalator:
    """
    Evaluates urgency based on deadline proximity and escalates notification priority.
    """

    @classmethod
    def evaluate_urgency(cls, deadline_date: Optional[datetime]) -> UrgencyLevel:
        """Evaluate deadline proximity relative to current UTC time."""
        if not deadline_date:
            return UrgencyLevel.NORMAL

        now = datetime.now(timezone.utc)
        if deadline_date.tzinfo is None:
            deadline_date = deadline_date.replace(tzinfo=timezone.utc)

        delta = deadline_date - now
        hours_remaining = delta.total_seconds() / 3600.0

        if hours_remaining <= 0:
            return UrgencyLevel.EXTREME
        elif hours_remaining < 6.0:
            return UrgencyLevel.EXTREME
        elif hours_remaining < 24.0:
            return UrgencyLevel.CRITICAL
        elif hours_remaining < 72.0:  # 3 days
            return UrgencyLevel.HIGH
        elif hours_remaining < 168.0:  # 7 days
            return UrgencyLevel.MEDIUM
        else:
            return UrgencyLevel.NORMAL

    @classmethod
    def escalate(
        cls,
        base_priority: str,
        relevance_score: int,
        deadline_date: Optional[datetime] = None,
        event_type: Optional[str] = None,
        is_watched_program: bool = False,
    ) -> PriorityLevel:
        """
        Determines final priority level based on opportunity priority,
        relevance score, deadline urgency, and event criticality.
        """
        urgency = cls.evaluate_urgency(deadline_date)
        norm_priority = (base_priority or "medium").strip().lower()

        # 1. CRITICAL Escalation:
        # - Urgency < 24h AND relevance >= 65
        if urgency in [UrgencyLevel.EXTREME, UrgencyLevel.CRITICAL] and relevance_score >= 65:
            return PriorityLevel.CRITICAL

        # - Critical event type + high relevance + watched program
        critical_events = [
            EventType.REGISTRATION_CLOSING.value,
            EventType.APPLICATION_DEADLINE.value,
            EventType.DEADLINE_CHANGED.value,
            EventType.DEADLINE_EXTENDED.value,
            EventType.DEADLINE_SHORTENED.value,
        ]
        if event_type in critical_events and relevance_score >= 80 and is_watched_program:
            return PriorityLevel.CRITICAL

        if norm_priority == "critical" and relevance_score >= 80:
            return PriorityLevel.CRITICAL

        # 2. HIGH Escalation:
        # - Urgency < 3 days AND relevance >= 70
        if urgency == UrgencyLevel.HIGH and relevance_score >= 70:
            return PriorityLevel.HIGH

        # - Registration opened on high relevance watched program
        if event_type in [EventType.REGISTRATION_OPEN.value, EventType.APPLICATION_OPEN.value] and relevance_score >= 85:
            return PriorityLevel.HIGH

        if norm_priority in ["critical", "high"] and relevance_score >= 75:
            return PriorityLevel.HIGH

        if relevance_score >= 90:
            return PriorityLevel.HIGH

        # 3. MEDIUM:
        if relevance_score >= 60 or norm_priority in ["critical", "high", "medium"]:
            return PriorityLevel.MEDIUM

        # 4. LOW:
        return PriorityLevel.LOW
