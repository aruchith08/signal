"""
Notification Throttler — Timezone-aware quiet hours and daily rate limit enforcement
"""
from datetime import datetime, timezone, time, timedelta
from typing import Optional, Tuple
from zoneinfo import ZoneInfo
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from apps.api.config import settings
from apps.api.models.notification import Notification
from shared.constants import PriorityLevel, NotificationStatus


class NotificationThrottler:
    """
    Evaluates quiet hours and daily delivery caps to prevent notification fatigue.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    COMMON_OFFSETS = {
        "Asia/Kolkata": timezone(timedelta(hours=5, minutes=30)),
        "IST": timezone(timedelta(hours=5, minutes=30)),
        "UTC": timezone.utc,
        "GMT": timezone.utc,
        "US/Eastern": timezone(timedelta(hours=-5)),
        "US/Pacific": timezone(timedelta(hours=-8)),
    }

    @classmethod
    def get_user_now(cls, tz_name: str) -> datetime:
        """Get current datetime in the user's timezone."""
        try:
            tz = ZoneInfo(tz_name)
            return datetime.now(tz)
        except Exception:
            offset_tz = cls.COMMON_OFFSETS.get(tz_name, cls.COMMON_OFFSETS["Asia/Kolkata"])
            return datetime.now(offset_tz)

    @classmethod
    def is_in_quiet_hours(
        cls,
        quiet_hours_start: str,
        quiet_hours_end: str,
        user_timezone: str = "Asia/Kolkata",
    ) -> bool:
        """
        Check if the current time in the user's timezone is within quiet hours.
        Supports windows that cross midnight (e.g. 22:30 -> 07:30).
        """
        try:
            start_parts = [int(p) for p in quiet_hours_start.split(":")]
            end_parts = [int(p) for p in quiet_hours_end.split(":")]
            start_time = time(start_parts[0], start_parts[1])
            end_time = time(end_parts[0], end_parts[1])

            user_now = cls.get_user_now(user_timezone)
            current_time = user_now.time()

            if start_time > end_time:
                # Overnight window (e.g. 22:30 -> 07:30)
                return current_time >= start_time or current_time < end_time
            else:
                # Same-day window (e.g. 13:00 -> 15:00)
                return start_time <= current_time < end_time
        except Exception:
            return False

    async def get_daily_sent_count(self, user_id: str, user_timezone: str = "Asia/Kolkata") -> int:
        """Count notifications dispatched to this user since midnight local time."""
        user_now = self.get_user_now(user_timezone)
        # Midnight of today in user's timezone
        local_midnight = user_now.replace(hour=0, minute=0, second=0, microsecond=0)
        # Convert to UTC for DB query
        utc_midnight = local_midnight.astimezone(timezone.utc)

        stmt = (
            select(func.count(Notification.id))
            .where(
                Notification.user_id == user_id,
                Notification.status.in_([NotificationStatus.SENT.value, NotificationStatus.DELIVERED.value]),
                Notification.sent_at >= utc_midnight,
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar() or 0

    async def evaluate_throttling(
        self,
        user_id: str,
        priority: PriorityLevel,
        quiet_hours_enabled: bool,
        quiet_hours_start: str = "22:30",
        quiet_hours_end: str = "07:30",
        user_timezone: str = "Asia/Kolkata",
        max_alerts_per_day: int = 10,
    ) -> Tuple[bool, bool, str]:
        """
        Evaluates rate limits and quiet hours.

        Returns:
            (is_rate_limited, is_in_quiet_hours, reason)
        """
        is_critical = priority == PriorityLevel.CRITICAL

        # 1. Daily Rate Limit Check
        daily_count = await self.get_daily_sent_count(user_id, user_timezone)
        if daily_count >= max_alerts_per_day:
            if is_critical and settings.SIGNAL_CRITICAL_ALERT_BYPASS_RATE_LIMIT:
                # Critical alert bypasses daily cap
                pass
            else:
                return True, False, f"Daily limit of {max_alerts_per_day} alerts reached ({daily_count} sent today)"

        # 2. Quiet Hours Check
        if quiet_hours_enabled:
            in_quiet = self.is_in_quiet_hours(quiet_hours_start, quiet_hours_end, user_timezone)
            if in_quiet:
                if is_critical and settings.SIGNAL_CRITICAL_ALERT_BYPASS_QUIET_HOURS:
                    # Critical alert bypasses quiet hours
                    return False, True, "In quiet hours, but bypassed due to CRITICAL priority"
                return False, True, f"In quiet hours ({quiet_hours_start} - {quiet_hours_end} {user_timezone})"

        return False, False, "Within rate limits and active notification hours"


# Compatibility alias
AntiFatigueEngine = NotificationThrottler
