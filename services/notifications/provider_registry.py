"""
Notification Provider Registry — Manages multi-channel notification providers
"""
import logging
from typing import Any, Dict, List, Optional, Union
from apps.api.config import settings
from services.notifications.base_notifier import BaseNotifier
from services.notifications.in_app_notifier import InAppNotifier
from services.notifications.mock_notifier import MockNotifier
from services.notifications.telegram import TelegramNotifier
from services.notifications.discord import DiscordNotifier
from services.notifications.email import EmailNotifier
from shared.constants import NotificationChannel

logger = logging.getLogger("signal.notifications.registry")


class NotificationProviderRegistry:
    """
    Central registry for multi-channel notification providers.
    Provides lifecycle, health checking, and provider resolution.
    """

    def __init__(self):
        self._providers: Dict[str, BaseNotifier] = {}
        self._initialize_defaults()

    def _initialize_defaults(self):
        # 1. In-App Provider
        self.register(NotificationChannel.IN_APP, InAppNotifier())

        # 2. Telegram Provider
        if settings.TELEGRAM_BOT_TOKEN:
            self.register(
                NotificationChannel.TELEGRAM,
                TelegramNotifier(bot_token=settings.TELEGRAM_BOT_TOKEN),
            )
        else:
            logger.info("Telegram provider registered in unconfigured/disabled state (no bot token).")

        # 3. Discord Provider
        self.register(NotificationChannel.DISCORD, DiscordNotifier())

        # 4. Email Provider
        self.register(NotificationChannel.EMAIL, EmailNotifier())

        # 5. Mock Provider (for test/local environments)
        self.register(NotificationChannel.MOCK, MockNotifier())

    def register(self, channel: Union[NotificationChannel, str], provider: BaseNotifier) -> None:
        key = channel.value if isinstance(channel, NotificationChannel) else str(channel).lower()
        self._providers[key] = provider
        logger.debug(f"[Registry] Registered provider '{provider.__class__.__name__}' for channel '{key}'")

    def get(self, channel: Union[NotificationChannel, str]) -> Optional[BaseNotifier]:
        key = channel.value if isinstance(channel, NotificationChannel) else str(channel).lower()
        return self._providers.get(key)

    def list_channels(self) -> List[str]:
        return list(self._providers.keys())

    async def get_provider_status(self) -> List[Dict[str, Any]]:
        """
        Runs health checks on all supported channels and returns structured status.
        """
        results = []
        channels = [
            NotificationChannel.IN_APP,
            NotificationChannel.TELEGRAM,
            NotificationChannel.DISCORD,
            NotificationChannel.EMAIL,
            NotificationChannel.MOCK,
        ]
        for ch in channels:
            key = ch.value
            provider = self._providers.get(key)
            if provider:
                try:
                    health = await provider.health_check()
                    is_healthy = health.get("status") == "healthy"
                    results.append({
                        "channel": key,
                        "enabled": True,
                        "healthy": is_healthy,
                        "provider_name": provider.__class__.__name__,
                        "details": health,
                    })
                except Exception as e:
                    results.append({
                        "channel": key,
                        "enabled": True,
                        "healthy": False,
                        "provider_name": provider.__class__.__name__,
                        "details": {"error": str(e)},
                    })
            else:
                results.append({
                    "channel": key,
                    "enabled": False,
                    "healthy": False,
                    "provider_name": None,
                    "details": {"reason": "Provider not configured or disabled"},
                })
        return results


# Global singleton registry
provider_registry = NotificationProviderRegistry()
