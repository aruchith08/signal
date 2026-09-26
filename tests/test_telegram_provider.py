"""
Tests for Telegram Message Formatter, MockNotifier, and TelegramNotifier
"""
import unittest
from datetime import datetime, timezone
from services.notifications.formatter import TelegramMessageFormatter
from services.notifications.mock_notifier import MockNotifier
from services.notifications.telegram import TelegramNotifier
from shared.constants import PriorityLevel


class TestTelegramProvider(unittest.IsolatedAsyncioTestCase):

    def test_markdown_escaping(self):
        raw = "TCS_CodeVita [2026] *Special* Edition"
        escaped = TelegramMessageFormatter.escape_markdown(raw)
        self.assertIn(r"\_", escaped)
        self.assertIn(r"\[", escaped)
        self.assertIn(r"\*", escaped)

    def test_format_alert_structure(self):
        msg = TelegramMessageFormatter.format_alert(
            title="Flipkart GRiD 6.0",
            score=94,
            reasons=["Matches Software Engineering", "High priority hackathon"],
            event_title="Registrations are now open",
            event_type="registration_open",
            organization_name="Flipkart",
            deadline=datetime(2026, 10, 15, 18, 30, tzinfo=timezone.utc),
            application_url="https://unstop.com/competitions/flipkart-grid-60",
            is_critical=True,
        )
        self.assertIn("🚨 *SIGNAL ALERT*", msg)
        self.assertIn("Flipkart GRiD 6.0", msg)
        self.assertIn("94%", msg)
        self.assertIn("Registrations are now open", msg)
        self.assertIn("15 October 2026", msg)
        self.assertIn("Flipkart", msg)
        self.assertIn("Apply / Learn More", msg)

    async def test_mock_notifier(self):
        notifier = MockNotifier()
        success = await notifier.send(
            recipient="chat_12345",
            message="Test message",
            priority=PriorityLevel.HIGH,
        )
        self.assertTrue(success)
        self.assertEqual(len(notifier.sent_messages), 1)
        self.assertEqual(notifier.sent_messages[0]["recipient"], "chat_12345")
        self.assertEqual(notifier.sent_messages[0]["priority"], "high")

        health = await notifier.health_check()
        self.assertEqual(health["status"], "healthy")
        self.assertEqual(health["messages_sent_count"], 1)

    async def test_telegram_notifier_missing_token(self):
        notifier = TelegramNotifier(bot_token="")
        # Should gracefully return False without raising an exception
        success = await notifier.send(recipient="12345", message="Hello")
        self.assertFalse(success)

        health = await notifier.health_check()
        self.assertEqual(health["status"], "unconfigured")


if __name__ == "__main__":
    unittest.main()
