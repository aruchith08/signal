"""
Mock Notifier for Local Development & Automated Tests
"""
import logging
from typing import Any, Dict, List, Optional
from services.notifications.base_notifier import BaseNotifier
from shared.constants import NotificationChannel, PriorityLevel

logger = logging.getLogger(__name__)


class MockNotifier(BaseNotifier):
    """Logs notifications to console and records sent messages in-memory for testing."""

    def __init__(self):
        super().__init__(channel=NotificationChannel.MOCK)
        self.sent_messages: List[Dict[str, Any]] = []

    async def send(
        self,
        recipient: str,
        message: str,
        priority: PriorityLevel = PriorityLevel.MEDIUM,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        record = {
            "channel": self.channel.value,
            "recipient": recipient,
            "message": message,
            "priority": priority.value,
            "metadata": metadata or {},
        }
        self.sent_messages.append(record)
        logger.info(f"🔔 [SIGNAL NOTIFICATION - {priority.value.upper()}] To: {recipient} | Message: {message[:80]}...")
        return True

    async def health_check(self) -> Dict[str, Any]:
        return {
            "channel": self.channel.value,
            "status": "healthy",
            "messages_sent_count": len(self.sent_messages),
        }
