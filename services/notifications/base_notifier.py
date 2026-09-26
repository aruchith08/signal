"""
Base Notifier Interface for Alert Dispatch
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from shared.constants import NotificationChannel, PriorityLevel


class BaseNotifier(ABC):
    """Abstract interface for all notification channel delivery providers."""

    def __init__(self, channel: NotificationChannel):
        self.channel = channel

    @abstractmethod
    async def send(
        self,
        recipient: str,
        message: str,
        priority: PriorityLevel = PriorityLevel.MEDIUM,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Deliver an alert to the user over this channel."""
        pass

    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """Verify provider availability and connectivity."""
        pass
