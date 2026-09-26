"""
Telegram Bot Notification Provider
"""
import logging
from typing import Any, Dict, Optional
import httpx
from services.notifications.base_notifier import BaseNotifier
from shared.constants import NotificationChannel, PriorityLevel

logger = logging.getLogger(__name__)


class TelegramNotifier(BaseNotifier):
    """Dispatches markdown-formatted opportunity alerts via Telegram Bot API."""

    def __init__(self, bot_token: Optional[str] = None):
        super().__init__(channel=NotificationChannel.TELEGRAM)
        self.bot_token = bot_token

    async def send(
        self,
        recipient: str,
        message: str,
        priority: PriorityLevel = PriorityLevel.MEDIUM,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        if not self.bot_token:
            logger.warning("Telegram bot token not configured. Skipping delivery.")
            return False

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": recipient,
            "text": message,
            "parse_mode": "Markdown",
            "disable_web_page_preview": False,
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, json=payload)
                if resp.status_code == 200:
                    logger.info(f"Telegram notification delivered to chat_id {recipient}")
                    return True
                logger.error(f"Telegram delivery failed ({resp.status_code}): {resp.text}")
                return False
        except Exception as exc:
            logger.error(f"Telegram request error: {exc}")
            return False

    async def health_check(self) -> Dict[str, Any]:
        """Check whether Telegram Bot token is valid by querying getMe."""
        if not self.bot_token:
            return {
                "channel": self.channel.value,
                "status": "unconfigured",
                "message": "TELEGRAM_BOT_TOKEN is not set",
            }

        url = f"https://api.telegram.org/bot{self.bot_token}/getMe"
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    data = resp.json().get("result", {})
                    return {
                        "channel": self.channel.value,
                        "status": "healthy",
                        "bot_username": data.get("username"),
                        "bot_id": data.get("id"),
                    }
                return {
                    "channel": self.channel.value,
                    "status": "degraded",
                    "error": resp.text,
                }
        except Exception as e:
            return {
                "channel": self.channel.value,
                "status": "failing",
                "error": str(e),
            }
