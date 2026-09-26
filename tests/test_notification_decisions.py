"""
Tests for NotificationDecisionEngine — Comprehensive decision pipeline validation
"""
import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from apps.api.models.base import Base
from apps.api.models.user import User, UserProfile, UserInterest
from apps.api.models.opportunity import Opportunity
from apps.api.models.event import OpportunityEvent
from apps.api.models.preference import UserNotificationPreference
from services.notifications.decision_engine import NotificationDecisionEngine
from services.notifications.throttling import NotificationThrottler
from shared.constants import DeliveryMode, PriorityLevel, EventType


class TestNotificationDecisions(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self.engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        self.session_factory = async_sessionmaker(bind=self.engine, class_=AsyncSession, expire_on_commit=False)

    async def asyncTearDown(self):
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await self.engine.dispose()

    async def _setup_user(self, session, is_active=True, notifs_enabled=True, min_score=70):
        user = User(
            email="testuser@example.com",
            username="testuser",
            is_active=is_active,
        )
        session.add(user)
        await session.flush()

        profile = UserProfile(
            user_id=user.id,
            education_level="Undergraduate",
            degree="B.Tech",
            branch="Computer Science",
            current_year=3,
        )
        session.add(profile)

        pref = UserNotificationPreference(
            user_id=user.id,
            enabled=notifs_enabled,
            min_relevance_score=min_score,
            quiet_hours_enabled=False,
            max_alerts_per_day=10,
        )
        session.add(pref)

        # Interest in competitive programming
        interest = UserInterest(
            user_id=user.id,
            category="competitive_programming",
            tag="competitive_programming",
            weight=1.0,
        )
        session.add(interest)

        # Skill: Python
        from apps.api.models.skill import Skill, UserSkill
        skill = Skill(name="Python", slug="python")
        session.add(skill)
        await session.flush()
        user_skill = UserSkill(user_id=user.id, skill_id=skill.id)
        session.add(user_skill)

        await session.flush()
        user.preferences = pref
        user.profile = profile
        return user

    async def test_inactive_user_skipped(self):
        async with self.session_factory() as session:
            user = await self._setup_user(session, is_active=False)
            opp = Opportunity(
                title="TCS CodeVita",
                slug="tcs-codevita-test",
                category="competitive_programming",
                priority="critical",
            )
            session.add(opp)
            await session.commit()

            engine = NotificationDecisionEngine(session)
            decision = await engine.evaluate(user=user, opportunity=opp)
            self.assertFalse(decision.should_notify)
            self.assertEqual(decision.delivery_mode, DeliveryMode.SKIPPED)
            self.assertIn("inactive", decision.reason.lower())

    async def test_disabled_preferences_skipped(self):
        async with self.session_factory() as session:
            user = await self._setup_user(session, notifs_enabled=False)
            opp = Opportunity(
                title="TCS CodeVita",
                slug="tcs-codevita-test-2",
                category="competitive_programming",
                priority="critical",
            )
            session.add(opp)
            await session.commit()

            engine = NotificationDecisionEngine(session)
            decision = await engine.evaluate(user=user, opportunity=opp)
            self.assertFalse(decision.should_notify)
            self.assertEqual(decision.delivery_mode, DeliveryMode.SKIPPED)
            self.assertIn("disabled", decision.reason.lower())

    async def test_low_relevance_skipped(self):
        async with self.session_factory() as session:
            user = await self._setup_user(session, min_score=80)
            opp = Opportunity(
                title="Ancient History Fellowship",
                slug="history-fellowship",
                category="education_research",
                priority="low",
            )
            session.add(opp)
            await session.commit()

            engine = NotificationDecisionEngine(session)
            decision = await engine.evaluate(user=user, opportunity=opp)
            self.assertFalse(decision.should_notify)
            self.assertEqual(decision.delivery_mode, DeliveryMode.SKIPPED)
            self.assertIn("below user threshold", decision.reason.lower())

    async def test_high_relevance_instant_delivery(self):
        async with self.session_factory() as session:
            user = await self._setup_user(session, min_score=70)
            opp = Opportunity(
                title="CodeChef Starters 150",
                slug="codechef-starters-150",
                category="competitive_programming",
                priority="high",
                required_skills="python",
                eligibility="Open to undergraduate students",
            )
            session.add(opp)
            await session.flush()

            event = OpportunityEvent(
                opportunity_id=opp.id,
                event_type=EventType.REGISTRATION_OPEN.value,
                title="Registrations are now open",
                deadline_date=datetime.now(timezone.utc) + timedelta(days=2),
            )
            session.add(event)
            await session.commit()

            # Mock daytime hours (not in quiet hours)
            with patch.object(NotificationThrottler, "is_in_quiet_hours", return_value=False):
                engine = NotificationDecisionEngine(session)
                decision = await engine.evaluate(user=user, opportunity=opp, event=event)
                self.assertTrue(decision.should_notify)
                self.assertEqual(decision.delivery_mode, DeliveryMode.INSTANT)
                self.assertGreaterEqual(decision.relevance_result.score, 70)

    async def test_quiet_hours_queues_notification(self):
        async with self.session_factory() as session:
            user = await self._setup_user(session, min_score=70)
            user.preferences.quiet_hours_enabled = True
            await session.commit()

            opp = Opportunity(
                title="CodeChef Starters 150",
                slug="codechef-starters-quiet",
                category="competitive_programming",
                priority="medium",
                required_skills="python",
                eligibility="Open to undergraduate students",
            )
            session.add(opp)
            await session.flush()

            event = OpportunityEvent(
                opportunity_id=opp.id,
                event_type=EventType.ANNOUNCED.value,
                title="Contest Announced",
            )
            session.add(event)
            await session.commit()

            with patch.object(NotificationThrottler, "is_in_quiet_hours", return_value=True):
                engine = NotificationDecisionEngine(session)
                decision = await engine.evaluate(user=user, opportunity=opp, event=event)
                self.assertTrue(decision.should_notify)
                self.assertEqual(decision.delivery_mode, DeliveryMode.QUEUED)
                self.assertIsNotNone(decision.scheduled_for)


if __name__ == "__main__":
    unittest.main()
