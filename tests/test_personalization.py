"""
Tests for User Profile, Interests, Skills, Preferences Models & APIs
"""
import unittest
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select

from apps.api.models.base import Base
from apps.api.models.user import User, UserProfile, UserInterest
from apps.api.models.skill import Skill, UserSkill
from apps.api.models.preference import UserNotificationPreference


class TestPersonalizationModels(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self.engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        self.session_factory = async_sessionmaker(bind=self.engine, class_=AsyncSession, expire_on_commit=False)

    async def asyncTearDown(self):
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await self.engine.dispose()

    async def test_user_creation_with_profile_and_preferences(self):
        async with self.session_factory() as session:
            user = User(
                email="student@example.com",
                username="tech_student",
                full_name="Aarav Sharma",
            )
            session.add(user)
            await session.flush()

            profile = UserProfile(
                user_id=user.id,
                education_level="Undergraduate",
                degree="B.Tech",
                branch="Computer Science",
                current_year=3,
                graduation_year=2026,
                country="India",
                timezone="Asia/Kolkata",
                career_interests="Software Engineering, AI",
                preferred_opportunity_types="competitive_programming,hackathon",
            )
            session.add(profile)

            pref = UserNotificationPreference(
                user_id=user.id,
                enabled=True,
                min_relevance_score=75,
                max_alerts_per_day=5,
                quiet_hours_enabled=True,
                quiet_hours_start="23:00",
                quiet_hours_end="07:00",
                telegram_chat_id="123456789",
                telegram_username="aarav_dev",
            )
            session.add(pref)
            await session.commit()

        # Query and verify
        async with self.session_factory() as session:
            loaded_user = (
                await session.execute(
                    select(User).where(User.username == "tech_student")
                )
            ).scalars().first()

            self.assertIsNotNone(loaded_user)
            self.assertEqual(loaded_user.full_name, "Aarav Sharma")
            self.assertEqual(loaded_user.profile.degree, "B.Tech")
            self.assertEqual(loaded_user.profile.current_year, 3)
            self.assertEqual(loaded_user.preferences.min_relevance_score, 75)
            self.assertEqual(loaded_user.preferences.telegram_chat_id, "123456789")

    async def test_weighted_interests_storage(self):
        async with self.session_factory() as session:
            user = User(email="coder@example.com", username="coder123")
            session.add(user)
            await session.flush()

            i1 = UserInterest(user_id=user.id, category="competitive_programming", tag="competitive_programming", weight=1.0)
            i2 = UserInterest(user_id=user.id, category="ai_ml", tag="machine_learning", weight=0.85)
            i3 = UserInterest(user_id=user.id, category="hackathons", tag="hackathons", weight=0.9)
            session.add_all([i1, i2, i3])
            await session.commit()

        async with self.session_factory() as session:
            interests = (
                await session.execute(
                    select(UserInterest).where(UserInterest.user_id == user.id)
                )
            ).scalars().all()

            self.assertEqual(len(interests), 3)
            weights = {i.tag: i.weight for i in interests}
            self.assertEqual(weights["competitive_programming"], 1.0)
            self.assertEqual(weights["machine_learning"], 0.85)
            self.assertEqual(weights["hackathons"], 0.9)

    async def test_user_skills_relationship(self):
        async with self.session_factory() as session:
            user = User(email="dev@example.com", username="fullstack_dev")
            session.add(user)
            await session.flush()

            skill_py = Skill(name="Python", slug="python", category="languages")
            skill_cpp = Skill(name="C++", slug="cpp", category="languages")
            session.add_all([skill_py, skill_cpp])
            await session.flush()

            us1 = UserSkill(user_id=user.id, skill_id=skill_py.id, proficiency_level="expert")
            us2 = UserSkill(user_id=user.id, skill_id=skill_cpp.id, proficiency_level="advanced")
            session.add_all([us1, us2])
            await session.commit()

        async with self.session_factory() as session:
            loaded_user = (
                await session.execute(
                    select(User).where(User.username == "fullstack_dev")
                )
            ).scalars().first()

            self.assertEqual(len(loaded_user.skills), 2)
            skill_names = [us.skill.name for us in loaded_user.skills]
            self.assertIn("Python", skill_names)
            self.assertIn("C++", skill_names)


if __name__ == "__main__":
    unittest.main()
