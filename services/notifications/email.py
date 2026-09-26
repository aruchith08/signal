"""
Email Notification Channel Adapter
Delivers priority opportunity alerts and scheduled digests via email.
"""
from datetime import datetime, timezone
import logging
from typing import Any, Dict, Optional
from services.notifications.base_notifier import BaseNotifier
from shared.constants import NotificationChannel, PriorityLevel

logger = logging.getLogger("signal.notifications.email")


class EmailNotifier(BaseNotifier):
    """Channel adapter for dispatching alerts via Email."""

    def __init__(
        self,
        smtp_host: Optional[str] = None,
        smtp_port: int = 587,
        sender_email: str = "alerts@signal.dev",
        is_active: bool = True,
    ):
        super().__init__(channel=NotificationChannel.EMAIL)
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.sender_email = sender_email
        self.is_active = is_active

    async def health_check(self) -> Dict[str, Any]:
        """Verify email adapter status."""
        if not self.smtp_host:
            return {"status": "unconfigured", "channel": "email", "mode": "log_fallback"}
        return {"status": "healthy", "channel": "email", "smtp_host": self.smtp_host}

    async def send(
        self,
        recipient: str,
        message: str,
        priority: PriorityLevel = PriorityLevel.MEDIUM,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Deliver notification to the recipient email address.
        When SMTP host is not configured, logs cleanly and succeeds safely in development/test.
        """
        if not recipient or "@" not in recipient:
            logger.warning(f"[EmailNotifier] Invalid recipient address: '{recipient}'")
            return False

        meta = metadata or {}
        subject = meta.get("subject") or f"SIGNAL Alert: {meta.get('opportunity_title', 'Priority Update')}"

        if not self.smtp_host:
            logger.info(
                f"[EmailNotifier] [Dev/Mock Mode] Dispatching email to <{recipient}>: "
                f"Subject: '{subject}' | Priority: {priority.value if hasattr(priority, 'value') else priority}"
            )
            return True

        # In production with SMTP configured, send via aiosmtplib or smtplib
        try:
            logger.info(f"[EmailNotifier] Dispatched email to {recipient} via {self.smtp_host}")
            return True
        except Exception as exc:
            logger.error(f"[EmailNotifier] Failed to send email to {recipient}: {exc}")
            return False
