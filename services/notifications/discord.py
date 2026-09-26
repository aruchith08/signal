"""
Discord Webhook Notification Channel Adapter
Delivers rich embedded priority opportunity alerts to Discord server channels or DMs.
"""
from datetime import datetime, timezone
import logging
from typing import Any, Dict, Optional
from services.ingestion.http_client import ResilientHTTPClient
from services.notifications.base_notifier import BaseNotifier
from shared.constants import NotificationChannel, PriorityLevel

logger = logging.getLogger("signal.notifications.discord")

# Priority-to-color mapping for Discord Embeds
COLOR_MAP = {
    PriorityLevel.CRITICAL: 0xE11D48,  # Red/Rose
    PriorityLevel.HIGH: 0xF59E0B,      # Amber
    PriorityLevel.MEDIUM: 0x3B82F6,    # Sky Blue
    PriorityLevel.LOW: 0x64748B,       # Slate
}


class DiscordNotifier(BaseNotifier):
    """Channel adapter for dispatching alerts via Discord Webhooks."""

    def __init__(self, default_webhook_url: Optional[str] = None):
        super().__init__(channel=NotificationChannel.DISCORD)
        self.default_webhook_url = default_webhook_url

    async def health_check(self) -> Dict[str, Any]:
        """Verify Discord connectivity or webhook validity."""
        if not self.default_webhook_url:
            return {"status": "unconfigured", "channel": "discord", "message": "No webhook URL configured"}
        try:
            async with ResilientHTTPClient(timeout=5.0) as client:
                res = await client.get(self.default_webhook_url)
                return {"status": "healthy" if res.status_code == 200 else "degraded", "channel": "discord"}
        except Exception as exc:
            return {"status": "unhealthy", "channel": "discord", "error": str(exc)}

    async def send(
        self,
        recipient: str,
        message: str,
        priority: PriorityLevel = PriorityLevel.MEDIUM,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Send a notification to a Discord webhook URL.
        `recipient` should be a Discord webhook URL, or falls back to `self.default_webhook_url`.
        """
        webhook_url = recipient if (recipient and recipient.startswith("https://discord.com/api/webhooks/")) else self.default_webhook_url
        if not webhook_url:
            logger.warning("[DiscordNotifier] Cannot send alert: No valid Discord webhook URL provided.")
            return False

        meta = metadata or {}
        opp_title = meta.get("opportunity_title") or "Opportunity Update"
        category = meta.get("category", "General")
        deadline = meta.get("deadline", "N/A")
        app_url = meta.get("application_url", "")
        color = COLOR_MAP.get(priority, 0x3B82F6)

        embed = {
            "title": f"📡 {opp_title}",
            "description": message,
            "url": app_url or None,
            "color": color,
            "fields": [
                {"name": "Category", "value": str(category).title(), "inline": True},
                {"name": "Priority", "value": str(priority.value if hasattr(priority, 'value') else priority).upper(), "inline": True},
                {"name": "Deadline", "value": str(deadline), "inline": True},
            ],
            "footer": {"text": "SIGNAL 📡 — Opportunity Intelligence Network"},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        payload = {
            "username": "SIGNAL Intelligence",
            "embeds": [embed],
        }

        try:
            async with ResilientHTTPClient(timeout=10.0) as client:
                res = await client.post(webhook_url, json=payload)
                if res.status_code in (200, 204):
                    logger.info(f"[DiscordNotifier] Alert successfully delivered for '{opp_title}'")
                    return True
                else:
                    logger.warning(f"[DiscordNotifier] Delivery failed with HTTP {res.status_code}: {res.text}")
                    return False
        except Exception as exc:
            logger.warning(f"[DiscordNotifier] Failed to post alert to Discord: {exc}")
            return False
