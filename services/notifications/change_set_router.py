"""
ChangeSet Notification Router — Bridges Opportunity Changes & Events to Multi-User Notifications
"""
import logging
from typing import List, Optional, Sequence, Set
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from apps.api.models.change_set import ChangeSet
from apps.api.models.event import OpportunityEvent
from apps.api.models.interaction import UserOpportunityInteraction
from apps.api.models.notification import Notification
from apps.api.models.opportunity import Opportunity
from apps.api.models.preference import UserNotificationPreference
from apps.api.models.skill import UserSkill
from apps.api.models.user import User
from services.notifications.base_notifier import BaseNotifier
from services.notifications.decision_engine import NotificationDecisionEngine
from services.notifications.dispatcher import NotificationDispatcher
from shared.constants import PriorityLevel, DeliveryMode

logger = logging.getLogger("signal.notifications.change_set_router")


class ChangeSetNotificationRouter:
    """
    Evaluates incoming Opportunity ChangeSets and OpportunityEvents to route targeted,
    anti-fatigue notifications to candidate users.
    """

    def __init__(self, provider: Optional[BaseNotifier] = None):
        self.provider = provider

    async def route_opportunity_activity(
        self,
        session: AsyncSession,
        opportunity: Opportunity,
        change_sets: Optional[Sequence[ChangeSet]] = None,
        event: Optional[OpportunityEvent] = None,
    ) -> List[Notification]:
        """
        Main entrypoint: identifies relevant candidate users, evaluates their notification
        decisions, and dispatches approved alerts.
        """
        change_sets = change_sets or []
        if not change_sets and not event:
            logger.debug(f"[ChangeSetRouter] No changesets or events for opp {opportunity.id}; skipping.")
            return []

        # 1. Discover candidate user IDs
        candidate_user_ids = await self._discover_candidate_user_ids(session, opportunity)
        if not candidate_user_ids:
            logger.info(f"[ChangeSetRouter] No eligible candidate users found for opp {opportunity.id}")
            return []

        # 2. Load candidate users with related profiles & preferences
        user_stmt = (
            select(User)
            .where(User.id.in_(candidate_user_ids), User.is_active == True)
            .options(
                selectinload(User.profile),
                selectinload(User.preferences),
                selectinload(User.interests),
                selectinload(User.skills).selectinload(UserSkill.skill),
                selectinload(User.interactions),
            )
        )
        candidates = (await session.execute(user_stmt)).scalars().all()

        decision_engine = NotificationDecisionEngine(session)
        dispatcher = NotificationDispatcher(session, provider=self.provider)

        dispatched_notifications: List[Notification] = []

        # 3. Evaluate each candidate user
        for user in candidates:
            try:
                # 3a. Strict deduplication check before proceeding
                event_id = event.id if event else None
                if await decision_engine.deduplicator.is_duplicate(user.id, opportunity.id, event_id):
                    logger.debug(
                        f"[ChangeSetRouter] User {user.id} skipped due to deduplication/cooldown for opp {opportunity.id}"
                    )
                    continue

                # Check if user explicitly followed/saved this opportunity
                is_subscriber = any(
                    inter.opportunity_id == opportunity.id and (inter.is_followed or inter.is_saved)
                    for inter in (user.interactions or [])
                )

                decision = await decision_engine.evaluate(user, opportunity, event)

                # If user is a direct subscriber and change is critical/deadline-related, ensure notification
                if is_subscriber and not decision.should_notify and decision.reason.startswith("Relevance score"):
                    # Direct subscriber override for relevance score check: user explicitly asked to follow
                    decision.should_notify = True
                    decision.priority = PriorityLevel.HIGH
                    decision.delivery_mode = DeliveryMode.INSTANT
                    decision.reason = f"Subscribed user alert ({decision.reason})"

                if decision.should_notify:
                    notification = await dispatcher.dispatch(
                        user=user,
                        opportunity=opportunity,
                        decision=decision,
                        event=event,
                    )
                    if notification:
                        dispatched_notifications.append(notification)
            except Exception as e:
                logger.error(
                    f"[ChangeSetRouter] Failed evaluating/dispatching notification for user {user.id} on opp {opportunity.id}: {e}",
                    exc_info=True,
                )

        logger.info(
            f"[ChangeSetRouter] Processed {len(candidates)} candidates for opp {opportunity.id}: "
            f"dispatched {len(dispatched_notifications)} notifications."
        )
        return dispatched_notifications

    async def _discover_candidate_user_ids(
        self,
        session: AsyncSession,
        opportunity: Opportunity,
        max_candidates: int = 100,
    ) -> Set[str]:
        """
        Discovers candidate user IDs based on:
        1. Users who saved or followed this opportunity.
        2. Users with notification preferences enabled.
        """
        candidate_ids: Set[str] = set()

        # 1. Direct subscribers (Saved or Followed)
        subscriber_stmt = select(UserOpportunityInteraction.user_id).where(
            UserOpportunityInteraction.opportunity_id == opportunity.id,
            or_(
                UserOpportunityInteraction.is_saved == True,
                UserOpportunityInteraction.is_followed == True,
            ),
        )
        subscribers = (await session.execute(subscriber_stmt)).scalars().all()
        candidate_ids.update(subscribers)

        # 2. General active users with notifications enabled
        general_stmt = (
            select(User.id)
            .join(UserNotificationPreference, UserNotificationPreference.user_id == User.id, isouter=True)
            .where(
                User.is_active == True,
                or_(
                    UserNotificationPreference.enabled == True,
                    UserNotificationPreference.enabled.is_(None),  # Default is enabled
                ),
            )
            .limit(max_candidates)
        )
        active_users = (await session.execute(general_stmt)).scalars().all()
        candidate_ids.update(active_users)

        return candidate_ids
