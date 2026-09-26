"""
Delivery Retry System — Retries failed NotificationDelivery records with backoff
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from apps.api.models.notification import Notification
from apps.api.models.notification_delivery import NotificationDelivery
from services.notifications.provider_registry import NotificationProviderRegistry, provider_registry
from shared.constants import NotificationStatus, NotificationChannel

logger = logging.getLogger("signal.notifications.retry")

MAX_ATTEMPTS = 3
RETRY_BACKOFF_MINUTES = {
    1: 5,   # After attempt 1 fails, wait 5 minutes before attempt 2
    2: 15,  # After attempt 2 fails, wait 15 minutes before attempt 3
}


class NotificationRetryEngine:
    """
    Coordinates detection and re-delivery of failed NotificationDelivery records.
    Enforces deterministic maximum attempts (3) and timed exponential backoff.
    """

    def __init__(self, registry: Optional[NotificationProviderRegistry] = None):
        self.registry = registry or provider_registry

    async def get_retryable_deliveries(
        self,
        session: AsyncSession,
        limit: int = 50,
        ignore_backoff: bool = False,
    ) -> List[NotificationDelivery]:
        """
        Finds NotificationDelivery records eligible for retry:
        - Status is FAILED
        - attempt_count < MAX_ATTEMPTS
        - last_attempt_at satisfies the backoff window (unless ignore_backoff is True)
        """
        now = datetime.now(timezone.utc)
        stmt = (
            select(NotificationDelivery)
            .where(
                NotificationDelivery.status == NotificationStatus.FAILED.value,
                NotificationDelivery.attempt_count < MAX_ATTEMPTS,
            )
            .options(
                selectinload(NotificationDelivery.notification),
            )
            .order_by(NotificationDelivery.last_attempt_at.asc())
            .limit(limit)
        )
        candidates = (await session.execute(stmt)).scalars().all()

        eligible = []
        for deliv in candidates:
            if ignore_backoff:
                eligible.append(deliv)
                continue

            last_at = deliv.last_attempt_at
            if last_at is None:
                eligible.append(deliv)
                continue

            # Ensure timezone awareness for comparison
            if last_at.tzinfo is None:
                last_at = last_at.replace(tzinfo=timezone.utc)

            required_delay = RETRY_BACKOFF_MINUTES.get(deliv.attempt_count, 15)
            if (now - last_at).total_seconds() >= required_delay * 60:
                eligible.append(deliv)

        return eligible

    async def retry_delivery(
        self,
        delivery_id: str,
        session: AsyncSession,
    ) -> bool:
        """
        Executes a single delivery retry for a specified NotificationDelivery record.
        Updates attempt_count, last_attempt_at, status, and error_message.
        """
        stmt = (
            select(NotificationDelivery)
            .where(NotificationDelivery.id == delivery_id)
            .options(selectinload(NotificationDelivery.notification))
        )
        delivery = (await session.execute(stmt)).scalars().first()
        if not delivery:
            logger.warning(f"[RetryEngine] Delivery record '{delivery_id}' not found")
            return False

        if delivery.status == NotificationStatus.DELIVERED.value:
            logger.info(f"[RetryEngine] Delivery '{delivery_id}' is already DELIVERED; skipping")
            return True

        if delivery.attempt_count >= MAX_ATTEMPTS:
            logger.warning(
                f"[RetryEngine] Delivery '{delivery_id}' exceeded MAX_ATTEMPTS ({MAX_ATTEMPTS}); "
                f"marked as permanently failed"
            )
            return False

        notification = delivery.notification
        if not notification:
            logger.error(f"[RetryEngine] Parent notification missing for delivery '{delivery_id}'")
            return False

        # Resolve provider
        provider = self.registry.get(delivery.channel)
        if not provider:
            provider = self.registry.get(NotificationChannel.MOCK)

        if not provider:
            logger.error(f"[RetryEngine] No provider available for channel '{delivery.channel}'")
            delivery.attempt_count += 1
            delivery.last_attempt_at = datetime.now(timezone.utc)
            delivery.error_message = f"No provider registered for channel '{delivery.channel}'"
            await session.flush()
            return False

        recipient = delivery.channel_identifier or f"user_{notification.user_id}"
        message = notification.message
        now = datetime.now(timezone.utc)

        delivery.attempt_count += 1
        delivery.last_attempt_at = now

        try:
            success = await provider.send(
                recipient=recipient,
                message=message,
                metadata={
                    "notification_id": notification.id,
                    "delivery_id": delivery.id,
                    "attempt": delivery.attempt_count,
                    "is_retry": True,
                },
            )
            if success:
                delivery.status = NotificationStatus.DELIVERED.value
                delivery.delivered_at = now
                delivery.error_message = None
                notification.status = NotificationStatus.SENT.value
                notification.delivered_at = now
                logger.info(
                    f"[RetryEngine] Successfully retried delivery '{delivery.id}' "
                    f"(attempt {delivery.attempt_count})"
                )
            else:
                delivery.status = NotificationStatus.FAILED.value
                delivery.error_message = "Retry provider returned false"
                logger.warning(
                    f"[RetryEngine] Retry provider failed for delivery '{delivery.id}' "
                    f"(attempt {delivery.attempt_count})"
                )
        except Exception as exc:
            success = False
            delivery.status = NotificationStatus.FAILED.value
            delivery.error_message = str(exc)
            logger.error(
                f"[RetryEngine] Exception during retry delivery '{delivery.id}': {exc}",
                exc_info=True,
            )

        await session.flush()
        return success

    async def process_retry_batch(
        self,
        session: AsyncSession,
        limit: int = 50,
        ignore_backoff: bool = False,
    ) -> Dict[str, Any]:
        """
        Scans for eligible retry records and processes each in the batch.
        """
        eligible = await self.get_retryable_deliveries(session, limit=limit, ignore_backoff=ignore_backoff)
        logger.info(f"[RetryEngine] Found {len(eligible)} eligible deliveries for retry")

        succeeded = 0
        failed = 0

        for deliv in eligible:
            try:
                ok = await self.retry_delivery(deliv.id, session)
                if ok:
                    succeeded += 1
                else:
                    failed += 1
            except Exception as e:
                logger.error(f"[RetryEngine] Unexpected error retrying delivery '{deliv.id}': {e}", exc_info=True)
                failed += 1

        return {
            "eligible": len(eligible),
            "succeeded": succeeded,
            "failed": failed,
        }
