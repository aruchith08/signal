"""
End-to-End Integration Tests for Phase 2: Personalization & Telegram Alerts
"""
import unittest
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select

from apps.api.models.base import Base
from apps.api.models.user import User, UserProfile, UserInterest
from apps.api.models.skill import Skill, UserSkill
from apps.api.models.preference import UserNotificationPreference
from apps.api.models.opportunity import Opportunity
from apps.api.models.event import OpportunityEvent
from apps.api.models.discovery import RawDiscovery
from apps.api.models.program_watch import ProgramWatch, ProgramWatchMatch
from apps.api.models.notification import Notification
from services.personalization.relevance_engine import PersonalizationEngine
from services.notifications.decision_engine import NotificationDecisionEngine
from services.notifications.dispatcher import NotificationDispatcher
from services.notifications.mock_notifier import MockNotifier
from services.notifications.telegram_bot import TelegramBotHandler
from shared.constants import (
    DeliveryMode,
    PriorityLevel,
    NotificationStatus,
    EventType,
    WatchPriority,
    WatchMatchLevel,
)


class TestPhase2Integration(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self.engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        self.session_factory = async_sessionmaker(bind=self.engine, class_=AsyncSession, expire_on_commit=False)

    async def asyncTearDown(self):
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await self.engine.dispose()

    async def test_end_to_end_personalization_to_dispatch(self):
        async with self.session_factory() as session:
            # 1. Create User
            user = User(
                email="aarav@university.edu",
                username="aarav_coder",
                full_name="Aarav Sharma",
                is_active=True,
            )
            session.add(user)
            await session.flush()

            profile = UserProfile(
                user_id=user.id,
                education_level="Undergraduate",
                degree="B.Tech",
                branch="Computer Science",
                current_year=2,
                graduation_year=2027,
                country="India",
                timezone="Asia/Kolkata",
            )
            session.add(profile)

            pref = UserNotificationPreference(
                user_id=user.id,
                enabled=True,
                min_relevance_score=70,
                telegram_chat_id="tg_987654321",
                telegram_username="aarav_coder",
            )
            session.add(pref)

            # Interests: Competitive Programming (1.0)
            interest = UserInterest(
                user_id=user.id,
                category="competitive_programming",
                tag="competitive_programming",
                weight=1.0,
            )
            session.add(interest)

            # Skill: Python
            skill = Skill(name="Python", slug="python", category="languages")
            session.add(skill)
            await session.flush()
            user_skill = UserSkill(user_id=user.id, skill_id=skill.id, proficiency_level="advanced")
            session.add(user_skill)

            # 2. Create Opportunity (TCS CodeVita)
            opp = Opportunity(
                title="TCS CodeVita Season 13",
                canonical_name="TCS CodeVita",
                slug="tcs-codevita-season-13",
                category="competitive_programming",
                priority="critical",
                eligibility="Open to all undergraduate engineering students",
                required_skills="python, c++, java",
                application_url="https://codevita.tcsapps.com",
            )
            session.add(opp)
            await session.flush()

            # Create Discovery and Program Watch Match
            discovery = RawDiscovery(
                original_url="https://codevita.tcsapps.com",
                canonical_url="https://codevita.tcsapps.com",
                raw_title="TCS CodeVita Season 13 Registration",
                raw_content="Registrations are now open for TCS CodeVita 2026",
                content_hash="abc123hash",
                status="processed",
                opportunity_id=opp.id,
            )
            session.add(discovery)
            await session.flush()

            watch = ProgramWatch(
                name="TCS CodeVita",
                canonical_name="tcs-codevita",
                priority=WatchPriority.CRITICAL.value,
                is_active=True,
            )
            session.add(watch)
            await session.flush()

            watch_match = ProgramWatchMatch(
                program_watch_id=watch.id,
                raw_discovery_id=discovery.id,
                match_score=1.0,
                match_level=WatchMatchLevel.EXACT_NAME.value,
                match_reason="Exact name match",
            )
            session.add(watch_match)

            # Create Lifecycle Event
            event = OpportunityEvent(
                opportunity_id=opp.id,
                source_discovery_id=discovery.id,
                event_type=EventType.REGISTRATION_OPEN.value,
                title="Registrations are now open",
                deadline_date=datetime.now(timezone.utc) + timedelta(days=5),
                is_critical=True,
                source_url="https://codevita.tcsapps.com",
            )
            session.add(event)
            await session.commit()

        # 3. Test Personalization & Relevance
        async with self.session_factory() as session:
            from sqlalchemy.orm import selectinload
            loaded_user = (
                await session.execute(
                    select(User)
                    .where(User.username == "aarav_coder")
                    .options(
                        selectinload(User.profile),
                        selectinload(User.preferences),
                        selectinload(User.interests),
                        selectinload(User.skills).selectinload(UserSkill.skill),
                    )
                )
            ).scalars().first()
            loaded_opp = (await session.execute(select(Opportunity).where(Opportunity.slug == "tcs-codevita-season-13"))).scalars().first()
            loaded_event = (await session.execute(select(OpportunityEvent).where(OpportunityEvent.opportunity_id == loaded_opp.id))).scalars().first()

            personalization = PersonalizationEngine(session)
            relevance = await personalization.evaluate_relevance(loaded_user, loaded_opp, loaded_event)

            self.assertGreaterEqual(relevance.score, 90)
            self.assertEqual(relevance.eligibility_status.value, "eligible")
            self.assertIn("competitive_programming", relevance.matched_interests)
            self.assertIn("python", relevance.matched_skills)
            self.assertIn("TCS CodeVita", relevance.matched_programs)

            # 4. Test Notification Decision Engine
            decision_engine = NotificationDecisionEngine(session)
            decision = await decision_engine.evaluate(loaded_user, loaded_opp, loaded_event)

            self.assertTrue(decision.should_notify)
            self.assertEqual(decision.delivery_mode, DeliveryMode.INSTANT)
            self.assertEqual(decision.priority, PriorityLevel.CRITICAL)

            # 5. Test Notification Dispatcher
            mock_provider = MockNotifier()
            dispatcher = NotificationDispatcher(session, provider=mock_provider)
            notification = await dispatcher.dispatch(
                user=loaded_user,
                opportunity=loaded_opp,
                decision=decision,
                event=loaded_event,
            )
            await session.commit()

            self.assertIsNotNone(notification)
            self.assertEqual(notification.status, NotificationStatus.SENT.value)
            self.assertEqual(len(mock_provider.sent_messages), 1)
            self.assertIn("TCS CodeVita", mock_provider.sent_messages[0]["message"])
            self.assertIn("tg_987654321", mock_provider.sent_messages[0]["recipient"])

            # 6. Test Deduplication on repeated poll
            repeat_decision = await decision_engine.evaluate(loaded_user, loaded_opp, loaded_event)
            self.assertFalse(repeat_decision.should_notify)
            self.assertEqual(repeat_decision.delivery_mode, DeliveryMode.SKIPPED)
            self.assertIn("already delivered", repeat_decision.reason.lower())

    async def test_telegram_bot_commands(self):
        async with self.session_factory() as session:
            bot = TelegramBotHandler(session)

            # Test /start
            start_reply = await bot.handle_command(
                chat_id="11223344",
                command_text="/start",
                username="new_coder",
                full_name="New Coder",
            )
            self.assertIn("Welcome to *SIGNAL*", start_reply)

            # Verify user and preferences created
            from sqlalchemy.orm import selectinload
            created_user = (
                await session.execute(
                    select(User)
                    .where(User.username == "new_coder")
                    .options(selectinload(User.preferences))
                )
            ).scalars().first()
            self.assertIsNotNone(created_user)
            self.assertEqual(created_user.preferences.telegram_chat_id, "11223344")

            # Test /status
            status_reply = await bot.handle_command(chat_id="11223344", command_text="/status")
            self.assertIn("Enabled", status_reply)
            self.assertIn("11223344", status_reply)

            # Test /unsubscribe
            unsub_reply = await bot.handle_command(chat_id="11223344", command_text="/unsubscribe")
            self.assertIn("Unsubscribed", unsub_reply)
            self.assertFalse(created_user.preferences.enabled)

            # Test /subscribe
            sub_reply = await bot.handle_command(chat_id="11223344", command_text="/subscribe")
            self.assertIn("Subscribed", sub_reply)
            self.assertTrue(created_user.preferences.enabled)


if __name__ == "__main__":
    unittest.main()
