"""
Tests for NotificationThrottler and PriorityEscalator
"""
import unittest
from datetime import datetime, timezone, timedelta, time
from unittest.mock import patch, MagicMock
from services.notifications.throttling import NotificationThrottler
from services.notifications.priority import PriorityEscalator
from shared.constants import PriorityLevel, UrgencyLevel, EventType


class TestNotificationThrottling(unittest.TestCase):

    def test_overnight_quiet_hours_detection(self):
        # 23:00 is within 22:30 -> 07:30
        dt_night = datetime(2026, 9, 12, 23, 0, 0)
        with patch.object(NotificationThrottler, "get_user_now", return_value=dt_night):
            in_quiet = NotificationThrottler.is_in_quiet_hours("22:30", "07:30", "Asia/Kolkata")
            self.assertTrue(in_quiet)

        # 03:00 is within 22:30 -> 07:30
        dt_early = datetime(2026, 9, 12, 3, 0, 0)
        with patch.object(NotificationThrottler, "get_user_now", return_value=dt_early):
            in_quiet = NotificationThrottler.is_in_quiet_hours("22:30", "07:30", "Asia/Kolkata")
            self.assertTrue(in_quiet)

        # 14:00 is NOT within 22:30 -> 07:30
        dt_day = datetime(2026, 9, 12, 14, 0, 0)
        with patch.object(NotificationThrottler, "get_user_now", return_value=dt_day):
            in_quiet = NotificationThrottler.is_in_quiet_hours("22:30", "07:30", "Asia/Kolkata")
            self.assertFalse(in_quiet)

    def test_daytime_quiet_hours_detection(self):
        # 14:30 is within 14:00 -> 16:00
        dt_afternoon = datetime(2026, 9, 12, 14, 30, 0)
        with patch.object(NotificationThrottler, "get_user_now", return_value=dt_afternoon):
            in_quiet = NotificationThrottler.is_in_quiet_hours("14:00", "16:00", "Asia/Kolkata")
            self.assertTrue(in_quiet)

        # 16:30 is NOT within 14:00 -> 16:00
        dt_late = datetime(2026, 9, 12, 16, 30, 0)
        with patch.object(NotificationThrottler, "get_user_now", return_value=dt_late):
            in_quiet = NotificationThrottler.is_in_quiet_hours("14:00", "16:00", "Asia/Kolkata")
            self.assertFalse(in_quiet)

    def test_urgency_evaluation(self):
        now = datetime.now(timezone.utc)

        # 3 hours remaining -> EXTREME
        deadline_3h = now + timedelta(hours=3)
        self.assertEqual(PriorityEscalator.evaluate_urgency(deadline_3h), UrgencyLevel.EXTREME)

        # 12 hours remaining -> CRITICAL
        deadline_12h = now + timedelta(hours=12)
        self.assertEqual(PriorityEscalator.evaluate_urgency(deadline_12h), UrgencyLevel.CRITICAL)

        # 2 days remaining -> HIGH
        deadline_2d = now + timedelta(days=2)
        self.assertEqual(PriorityEscalator.evaluate_urgency(deadline_2d), UrgencyLevel.HIGH)

        # 5 days remaining -> MEDIUM
        deadline_5d = now + timedelta(days=5)
        self.assertEqual(PriorityEscalator.evaluate_urgency(deadline_5d), UrgencyLevel.MEDIUM)

        # 10 days remaining -> NORMAL
        deadline_10d = now + timedelta(days=10)
        self.assertEqual(PriorityEscalator.evaluate_urgency(deadline_10d), UrgencyLevel.NORMAL)

    def test_priority_escalation(self):
        now = datetime.now(timezone.utc)
        deadline_8h = now + timedelta(hours=8)

        # High urgency (<24h) + relevant score -> CRITICAL
        p = PriorityEscalator.escalate(
            base_priority="medium",
            relevance_score=85,
            deadline_date=deadline_8h,
        )
        self.assertEqual(p, PriorityLevel.CRITICAL)

        # High relevance (95) -> HIGH
        p_high = PriorityEscalator.escalate(
            base_priority="low",
            relevance_score=95,
        )
        self.assertEqual(p_high, PriorityLevel.HIGH)


if __name__ == "__main__":
    unittest.main()
