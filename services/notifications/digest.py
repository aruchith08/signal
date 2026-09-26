"""
SIGNAL 📡 — Notification Digest Engine (Daily, Weekly, Urgent 48h)
Aggregates relevant opportunities for users and compiles personalized, anti-spam digest summaries.
Respects user preferences, quiet hours, relevance score ceilings, and anti-fatigue limits.
"""
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from enum import Enum
import logging
from typing import Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import selectinload

from apps.api.models.user import User
from apps.api.models.opportunity import Opportunity
from apps.api.models.event import OpportunityEvent
from apps.api.models.preference import UserNotificationPreference
from apps.api.models.notification import Notification
from services.notifications.throttling import AntiFatigueEngine
from services.personalization.relevance_engine import PersonalizationEngine
from services.notifications.provider_registry import provider_registry
from shared.constants import (
    NotificationChannel,
    NotificationStatus,
    PriorityLevel,
    OpportunityStatus,
)

logger = logging.getLogger("signal.notifications.digest")


class DigestType(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    URGENT_48H = "urgent_48h"


@dataclass
class DigestPayload:
    user_id: str
    digest_type: DigestType
    opportunity_count: int
    subject: str
    body: str
    opportunity_ids: List[str]


class DigestEngine:
    """Compiles and dispatches periodic personalized digest notifications."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.anti_fatigue = AntiFatigueEngine(db)
        self.relevance_engine = PersonalizationEngine(db)

    async def generate_user_digest(
        self,
        user: User,
        digest_type: DigestType = DigestType.DAILY,
        time_window_hours: int = 24,
    ) -> Optional[DigestPayload]:
        """
        Generate a personalized digest payload for a user.
        Returns None if user preferences disable digests, quiet hours are active, or no qualifying opportunities exist.
        """
        if user.id:
            user_stmt = (
                select(User)
                .where(User.id == user.id)
                .options(
                    selectinload(User.profile),
                    selectinload(User.preferences),
                    selectinload(User.interests),
                )
            )
            loaded_user = (await self.db.execute(user_stmt)).scalars().first()
            if loaded_user:
                user = loaded_user

        pref: Optional[UserNotificationPreference] = user.preferences
        if pref and not pref.enabled:
            return None
        if pref and digest_type == DigestType.DAILY and not pref.digest_enabled:
            return None

        # 1. Respect quiet hours
        if pref and pref.quiet_hours_enabled:
            now_utc = datetime.now(timezone.utc)
            current_hour = now_utc.hour
            start_h = pref.quiet_hours_start_utc or 22
            end_h = pref.quiet_hours_end_utc or 7
            if start_h > end_h:  # e.g., 22:00 to 07:00 next morning
                if current_hour >= start_h or current_hour < end_h:
                    logger.debug(f"[DigestEngine] Skipping user {user.id} during quiet hours ({start_h}:00 - {end_h}:00)")
                    return None
            else:
                if start_h <= current_hour < end_h:
                    return None

        # 2. Gather candidate opportunities
        now = datetime.now(timezone.utc)
        min_relevance = pref.min_relevance_score if pref else 60

        if digest_type == DigestType.URGENT_48H:
            # Opportunities with deadline in next 48h
            horizon = now + timedelta(hours=48)
            opp_stmt = (
                select(Opportunity)
                .join(OpportunityEvent, Opportunity.id == OpportunityEvent.opportunity_id)
                .options(selectinload(Opportunity.events))
                .where(
                    and_(
                        OpportunityEvent.deadline_date.isnot(None),
                        OpportunityEvent.deadline_date >= now,
                        OpportunityEvent.deadline_date <= horizon,
                        Opportunity.status != OpportunityStatus.CLOSED.value,
                    )
                )
                .distinct()
                .limit(20)
            )
        else:
            # New or active opportunities discovered within time_window
            window_start = now - timedelta(hours=time_window_hours)
            opp_stmt = (
                select(Opportunity)
                .options(selectinload(Opportunity.events))
                .where(
                    and_(
                        Opportunity.created_at >= window_start,
                        Opportunity.status != OpportunityStatus.CLOSED.value,
                    )
                )
                .order_by(Opportunity.created_at.desc())
                .limit(30)
            )

        candidates = (await self.db.execute(opp_stmt)).scalars().all()
        if not candidates:
            return None

        # 3. Score opportunities and rank
        scored_opps: List[tuple[Opportunity, int, List[str]]] = []
        for opp in candidates:
            res = await self.relevance_engine.evaluate_relevance(user, opp)
            if res.score >= min_relevance:
                scored_opps.append((opp, res.score, res.reasons))

        scored_opps.sort(key=lambda x: x[1], reverse=True)
        top_opps = scored_opps[:5]  # Top 5 curated items

        if not top_opps:
            return None

        # 4. Format digest content
        opp_ids = [opp.id for opp, _, _ in top_opps]
        count = len(top_opps)

        if digest_type == DigestType.URGENT_48H:
            subject = f"⏳ SIGNAL Urgent: {count} opportunities closing within 48 hours"
            header = f"**URGENT DEADLINE ALERT**\nThe following high-relevance opportunities are closing soon:\n"
        elif digest_type == DigestType.WEEKLY:
            subject = f"📅 SIGNAL Weekly Brief: Top {count} opportunities curated for you"
            header = f"**WEEKLY OPPORTUNITY INTELLIGENCE DIGEST**\nHere is your weekly summary of top opportunities matching your profile:\n"
        else:
            subject = f"📡 SIGNAL Daily Digest: {count} opportunities matching your profile"
            header = f"**DAILY OPPORTUNITY DIGEST**\nHere are top matching opportunities discovered today:\n"

        lines = [header]
        for idx, (opp, score, reasons) in enumerate(top_opps, 1):
            opp_deadline = None
            if hasattr(opp, "events") and opp.events:
                deadlines = [e.deadline_date for e in opp.events if e.deadline_date]
                if deadlines:
                    opp_deadline = deadlines[0]
            deadline_str = opp_deadline.strftime("%b %d, %Y") if opp_deadline else "Open"
            reason_str = f"Why: {reasons[0]}" if reasons else ""
            lines.append(
                f"{idx}. **[{opp.title}]({opp.application_url or ''})** (Score: {score}/100)\n"
                f"   Category: {opp.category} | Deadline: {deadline_str}\n"
                f"   {reason_str}\n"
            )

        body = "\n".join(lines)
        return DigestPayload(
            user_id=user.id,
            digest_type=digest_type,
            opportunity_count=count,
            subject=subject,
            body=body,
            opportunity_ids=opp_ids,
        )

    async def dispatch_digest(self, payload: DigestPayload) -> bool:
        """Deliver digest notification and record in Notification audit log."""
        channel = NotificationChannel.IN_APP
        notifier = provider_registry.get(channel)
        if not notifier:
            return False

        success = await notifier.send(
            recipient=payload.user_id,
            message=payload.body,
            priority=PriorityLevel.MEDIUM,
            metadata={
                "subject": payload.subject,
                "digest_type": payload.digest_type.value,
                "opportunity_ids": payload.opportunity_ids,
            },
        )

        # Audit notification record
        notif = Notification(
            user_id=payload.user_id,
            opportunity_id=payload.opportunity_ids[0] if payload.opportunity_ids else None,
            channel=channel.value,
            message=f"**{payload.subject}**\n\n{payload.body}",
            status=NotificationStatus.DELIVERED.value if success else NotificationStatus.FAILED.value,
            priority=PriorityLevel.MEDIUM.value,
            delivery_mode="digest",
        )
        self.db.add(notif)
        await self.db.flush()
        logger.info(f"[DigestEngine] Dispatched {payload.digest_type.value} digest to user {payload.user_id}")
        return success
