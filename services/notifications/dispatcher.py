"""
Notification Dispatcher — Handles provider routing and persistent audit logging
"""
import logging
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import inspect, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.config import settings
from apps.api.models.user import User
from apps.api.models.opportunity import Opportunity
from apps.api.models.event import OpportunityEvent
from apps.api.models.notification import Notification
from apps.api.models.notification_delivery import NotificationDelivery
from services.notifications.base_notifier import BaseNotifier
from services.notifications.mock_notifier import MockNotifier
from services.notifications.telegram import TelegramNotifier
from services.notifications.in_app_notifier import InAppNotifier
from services.notifications.formatter import TelegramMessageFormatter
from services.notifications.decision_engine import NotificationDecision
from shared.constants import NotificationChannel, NotificationStatus, DeliveryMode

logger = logging.getLogger("signal.notifications.dispatcher")


class NotificationDispatcher:
    """
    Coordinates delivery across notification providers (Telegram, Mock)
    and records auditable notification event trails.
    """

    def __init__(self, db: AsyncSession, provider: Optional[BaseNotifier] = None):
        self.db = db
        if provider:
            self.provider = provider
        elif settings.TELEGRAM_BOT_TOKEN and settings.SIGNAL_NOTIFICATION_PROVIDER == "telegram":
            self.provider = TelegramNotifier(bot_token=settings.TELEGRAM_BOT_TOKEN)
        else:
            self.provider = MockNotifier()

    async def dispatch(
        self,
        user: User,
        opportunity: Opportunity,
        decision: NotificationDecision,
        event: Optional[OpportunityEvent] = None,
    ) -> Optional[Notification]:
        """
        Dispatches an approved alert and records an audit log entry in the database.
        """
        if not decision.should_notify:
            logger.debug(f"[Dispatcher] Skipping notification for user {user.id}: {decision.reason}")
            return None

        # Double check exact duplicate prevention for user + event
        if event and event.id:
            dup_stmt = select(Notification).where(
                Notification.user_id == user.id,
                Notification.event_id == event.id,
            )
            existing_notif = (await self.db.execute(dup_stmt)).scalars().first()
            if existing_notif:
                logger.info(
                    f"[Dispatcher] Notification already exists for user {user.id} on event {event.id}; skipping duplicate."
                )
                return existing_notif

        # 1. Format Message
        reasons = decision.relevance_result.reasons if decision.relevance_result else []
        score = decision.relevance_result.score if decision.relevance_result else 75
        deadline = event.deadline_date if event else None
        event_title = event.title if event else None
        event_type = event.event_type if event else opportunity.current_state

        org_name = None
        try:
            opp_insp = inspect(opportunity)
            if "organization" not in opp_insp.unloaded and opportunity.organization:
                org_name = opportunity.organization.name
        except Exception:
            org_name = None

        app_url = opportunity.application_url or (event.source_url if event else None)
        is_crit = decision.priority.value == "critical"

        formatted_message = TelegramMessageFormatter.format_alert(
            title=opportunity.title,
            score=score,
            reasons=reasons,
            event_title=event_title,
            event_type=event_type,
            organization_name=org_name,
            deadline=deadline,
            application_url=app_url,
            is_critical=is_crit,
        )

        # 2. Determine Recipient Target
        chat_id = None
        try:
            user_insp = inspect(user)
            if "preferences" not in user_insp.unloaded and user.preferences:
                chat_id = getattr(user.preferences, "telegram_chat_id", None)
        except Exception:
            chat_id = None

        if not chat_id and settings.TELEGRAM_DEFAULT_CHAT_ID:
            chat_id = settings.TELEGRAM_DEFAULT_CHAT_ID
        elif not chat_id:
            chat_id = f"user_{user.id}"

        now = datetime.now(timezone.utc)
        channel_name = self.provider.channel.value

        # 3. Handle Delivery Modes
        if decision.delivery_mode == DeliveryMode.INSTANT:
            try:
                success = await self.provider.send(
                    recipient=chat_id,
                    message=formatted_message,
                    priority=decision.priority,
                    metadata={"opportunity_id": opportunity.id, "user_id": user.id},
                )
                status = NotificationStatus.SENT.value if success else NotificationStatus.FAILED.value
                delivery_status = NotificationStatus.DELIVERED.value if success else NotificationStatus.FAILED.value
                error_msg = None if success else "Provider delivery returned false"
            except Exception as e:
                logger.error(f"[Dispatcher] Delivery exception: {e}", exc_info=True)
                success = False
                status = NotificationStatus.FAILED.value
                delivery_status = NotificationStatus.FAILED.value
                error_msg = str(e)

            notification = Notification(
                user_id=user.id,
                opportunity_id=opportunity.id,
                event_id=event.id if event else None,
                channel=channel_name,
                priority=decision.priority.value,
                status=status,
                delivery_mode=decision.delivery_mode.value,
                relevance_score=float(score),
                decision_reason=decision.reason,
                message=formatted_message,
                error_message=error_msg,
                sent_at=now if success else None,
                delivered_at=now if success else None,
            )
            self.db.add(notification)
            await self.db.flush()

            delivery = NotificationDelivery(
                notification_id=notification.id,
                channel=channel_name,
                status=delivery_status,
                attempt_count=1,
                last_attempt_at=now,
                delivered_at=now if success else None,
                error_message=error_msg,
                channel_identifier=str(chat_id),
            )
            self.db.add(delivery)
            await self.db.flush()
        else:
            # QUEUED or DIGEST
            notification = Notification(
                user_id=user.id,
                opportunity_id=opportunity.id,
                event_id=event.id if event else None,
                channel=channel_name,
                priority=decision.priority.value,
                status=NotificationStatus.QUEUED.value,
                delivery_mode=decision.delivery_mode.value,
                relevance_score=float(score),
                decision_reason=decision.reason,
                message=formatted_message,
            )
            self.db.add(notification)
            await self.db.flush()

            delivery = NotificationDelivery(
                notification_id=notification.id,
                channel=channel_name,
                status=NotificationStatus.PENDING.value,
                attempt_count=0,
                last_attempt_at=None,
                delivered_at=None,
                error_message=None,
                channel_identifier=str(chat_id),
            )
            self.db.add(delivery)
            await self.db.flush()

        logger.info(
            f"[Dispatcher] Recorded notification '{notification.id}' ({notification.status}) "
            f"and delivery log '{delivery.id}' ({delivery.status}) for user {user.id} -> opp {opportunity.id}"
        )
        return notification
