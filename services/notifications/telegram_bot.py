"""
Telegram Bot Command Handler & User Linking Service
"""
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from apps.api.models.user import User, UserProfile, UserInterest
from apps.api.models.preference import UserNotificationPreference
from shared.constants import InterestCategory

logger = logging.getLogger("signal.notifications.telegram_bot")


class TelegramBotHandler:
    """
    Handles incoming Telegram webhook commands and links users with their Telegram chat.
    """

    WELCOME_MESSAGE = (
        "Welcome to *SIGNAL* 📡\n\n"
        "Your Personal Opportunity Intelligence Network.\n\n"
        "I monitor high-value opportunities for students and developers across:\n"
        "• TCS CodeVita & Corporate Challenges\n"
        "• Smart India Hackathon & National Contests\n"
        "• Codeforces, CodeChef, LeetCode, HackerRank\n"
        "• Google Summer of Code & Open Source\n"
        "• Internships, Scholarships & Fellowships\n\n"
        "Commands:\n"
        "• `/status` — View your monitoring status\n"
        "• `/preferences` — View your alert preferences\n"
        "• `/subscribe` — Enable instant opportunity alerts\n"
        "• `/unsubscribe` — Pause opportunity alerts\n"
        "• `/help` — Show command directory\n\n"
        "Your Telegram account has been linked to SIGNAL!"
    )

    HELP_MESSAGE = (
        "📡 *SIGNAL Bot Commands:*\n\n"
        "• `/start` — Welcome & account linking\n"
        "• `/status` — View active monitoring status & interests\n"
        "• `/preferences` — Show threshold and quiet hours settings\n"
        "• `/subscribe` — Turn ON opportunity alerts\n"
        "• `/unsubscribe` — Turn OFF opportunity alerts\n"
        "• `/help` — Show this message"
    )

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_or_create_telegram_user(
        self,
        chat_id: str,
        telegram_user_id: Optional[str] = None,
        username: Optional[str] = None,
        full_name: Optional[str] = None,
    ) -> User:
        """
        Finds existing user linked to chat_id or creates a new one with defaults.
        """
        # 1. Search existing preference by chat_id
        pref_stmt = select(UserNotificationPreference).where(
            UserNotificationPreference.telegram_chat_id == chat_id
        )
        pref = (await self.db.execute(pref_stmt)).scalars().first()

        if pref and pref.user:
            return pref.user

        from sqlalchemy.orm import selectinload

        # 2. Check by username or create fresh
        clean_user_handle = username or f"tg_{chat_id}"
        existing_user_stmt = (
            select(User)
            .where(User.username == clean_user_handle)
            .options(
                selectinload(User.profile),
                selectinload(User.preferences),
                selectinload(User.interests),
            )
        )
        existing_user = (await self.db.execute(existing_user_stmt)).scalars().first()

        now = datetime.now(timezone.utc)

        if existing_user:
            user = existing_user
        else:
            user = User(
                email=f"{clean_user_handle}@signal.local",
                username=clean_user_handle,
                full_name=full_name or clean_user_handle,
                is_active=True,
            )
            self.db.add(user)
            await self.db.flush()

            # Create default profile
            profile = UserProfile(
                user_id=user.id,
                education_level="Undergraduate",
                degree="B.Tech",
                branch="Computer Science",
                current_year=2,
                country="India",
                timezone="Asia/Kolkata",
            )
            self.db.add(profile)

            # Seed default interests
            default_interests = [
                ("competitive_programming", "competitive_programming", 1.0),
                ("hackathons", "hackathons", 0.90),
                ("ai_ml", "ai_ml", 0.85),
                ("open_source", "open_source", 0.80),
            ]
            for cat, tag, wt in default_interests:
                self.db.add(UserInterest(user_id=user.id, category=cat, tag=tag, weight=wt))

        # 3. Create or update preference record directly
        pref_check_stmt = select(UserNotificationPreference).where(UserNotificationPreference.user_id == user.id)
        existing_pref = (await self.db.execute(pref_check_stmt)).scalars().first()

        if not existing_pref:
            preference = UserNotificationPreference(
                user_id=user.id,
                enabled=True,
                min_relevance_score=70,
                instant_alerts_enabled=True,
                telegram_chat_id=chat_id,
                telegram_user_id=telegram_user_id or chat_id,
                telegram_username=username,
                telegram_linked_at=now,
            )
            self.db.add(preference)
            user.preferences = preference
        else:
            existing_pref.telegram_chat_id = chat_id
            existing_pref.telegram_user_id = telegram_user_id or chat_id
            existing_pref.telegram_username = username
            existing_pref.telegram_linked_at = now
            user.preferences = existing_pref

        await self.db.flush()
        return user

    async def handle_command(
        self,
        chat_id: str,
        command_text: str,
        telegram_user_id: Optional[str] = None,
        username: Optional[str] = None,
        full_name: Optional[str] = None,
    ) -> str:
        """
        Processes an incoming bot text command and returns the reply markdown.
        """
        user = await self.get_or_create_telegram_user(
            chat_id=chat_id,
            telegram_user_id=telegram_user_id,
            username=username,
            full_name=full_name,
        )

        cmd = command_text.strip().split()[0].lower() if command_text.strip() else ""

        if cmd in ["/start", "start"]:
            return self.WELCOME_MESSAGE

        elif cmd in ["/help", "help"]:
            return self.HELP_MESSAGE

        elif cmd in ["/status", "status"]:
            status_text = "Enabled" if (user.preferences and user.preferences.enabled) else "Paused"
            min_score = user.preferences.min_relevance_score if user.preferences else 70
            interests_list = [f"• {i.tag.replace('_', ' ').title()} (weight: {i.weight})" for i in (user.interests or [])]
            interests_str = "\n".join(interests_list) if interests_list else "• General Opportunities"

            return (
                "📡 *SIGNAL Status:*\n\n"
                f"• Notifications: *{status_text}*\n"
                f"• Min Relevance Threshold: *{min_score}%*\n"
                f"• Telegram Chat ID: `{chat_id}`\n\n"
                f"*Active Interests:*\n{interests_str}"
            )

        elif cmd in ["/subscribe", "subscribe"]:
            if user.preferences:
                user.preferences.enabled = True
                await self.db.flush()
            return "✅ *Subscribed!* SIGNAL will now send you real-time alerts for high-relevance opportunities."

        elif cmd in ["/unsubscribe", "unsubscribe"]:
            if user.preferences:
                user.preferences.enabled = False
                await self.db.flush()
            return "⏸ *Unsubscribed.* Alerts have been paused. You can re-enable anytime with `/subscribe`."

        elif cmd in ["/preferences", "preferences"]:
            p = user.preferences
            if not p:
                return "Preferences not found."
            quiet = f"Enabled ({p.quiet_hours_start} - {p.quiet_hours_end} {p.timezone})" if p.quiet_hours_enabled else "Disabled"
            return (
                "⚙️ *Your SIGNAL Preferences:*\n\n"
                f"• Instant Alerts: *{'Yes' if p.instant_alerts_enabled else 'No'}*\n"
                f"• Daily Digest: *{'Yes' if p.digest_enabled else 'No'}*\n"
                f"• Min Relevance Score: *{p.min_relevance_score}%*\n"
                f"• Max Alerts / Day: *{p.max_alerts_per_day}*\n"
                f"• Quiet Hours: *{quiet}*\n"
                f"• Timezone: *{p.timezone}*"
            )

        return (
            f"Unrecognized command: `{cmd}`\n\n"
            "Use `/help` to see available commands."
        )
