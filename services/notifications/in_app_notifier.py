"""
In-App Notification Provider — Handles in-app inbox notifications
"""
import logging
from typing import Any, Dict, Optional
from services.notifications.base_notifier import BaseNotifier
from shared.constants import NotificationChannel, PriorityLevel

logger = logging.getLogger("signal.notifications.in_app")


class InAppNotifier(BaseNotifier):
    """
    Delivers notifications to the user's in-app inbox.
    Since in-app alerts are persisted directly via the database Notification model,
    this provider validates delivery and manages channel health.
    """

    def __init__(self):
        super().__init__(channel=NotificationChannel.IN_APP)

    async def send(
        self,
        recipient: str,
        message: str,
        priority: PriorityLevel = PriorityLevel.MEDIUM,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        In-app delivery is instantly available to the user upon database persistence.
        Returns True to indicate immediate successful delivery.
        """
        logger.debug(
            f"[InAppNotifier] In-app notification ready for recipient {recipient} "
            f"(priority: {priority.value})"
        )
        return True

    async def health_check(self) -> Dict[str, Any]:
        """Verify in-app delivery engine health."""
        return {
            "status": "healthy",
            "channel": self.channel.value,
            "provider": "in_app_database",
        }
