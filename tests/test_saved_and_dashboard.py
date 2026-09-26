"""
Unit & Integration Tests for Phase 4 Saved Opportunities and Dashboard Overview
"""
import sys
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from apps.api.main import app
from apps.api.database import get_db, Base
from apps.api.models.opportunity import Opportunity
from apps.api.models.event import OpportunityEvent
from apps.api.models.organization import Organization
from shared.constants import OpportunityCategory, OpportunityStatus, VerificationStatus


class TestSavedAndDashboard(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
        self.session_factory = async_sessionmaker(
            bind=self.engine, class_=AsyncSession, expire_on_commit=False
        )
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async def override_get_db():
            async with self.session_factory() as session:
                yield session

        app.dependency_overrides[get_db] = override_get_db
        self.transport = ASGITransport(app=app)

        # Pre-populate an organization, an opportunity, and an event
        async with self.session_factory() as session:
            org = Organization(name="TCS", slug="tcs", is_verified=True)
            session.add(org)
            await session.flush()

            opp = Opportunity(
                title="TCS CodeVita Season 14",
                canonical_name="tcs codevita season 14",
                slug="tcs-codevita-season-14",
                organization_id=org.id,
                category=OpportunityCategory.COMPETITIVE_PROGRAMMING.value,
                event_type="competition",
                status=OpportunityStatus.REGISTRATION_OPEN.value,
                verification_status=VerificationStatus.VERIFIED.value,
                confidence_score=95,
                verification_confidence=0.95,
                source_count=2,
                official_source_present=True,
                year=2026,
            )
            session.add(opp)
            await session.flush()

            evt = OpportunityEvent(
                opportunity_id=opp.id,
                event_type="registration_closing",
                title="CodeVita Registration Closes",
                deadline_date=datetime.now(timezone.utc) + timedelta(days=5),
                is_critical=True,
            )
            session.add(evt)
            await session.commit()
            self.opp_id = opp.id
            self.org_id = org.id

    async def asyncTearDown(self):
        app.dependency_overrides.clear()
        await self.engine.dispose()

    async def test_get_active_user_bootstraps_demo(self):
        async with AsyncClient(transport=self.transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/users/active")
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertEqual(data["username"], "alex_chen")
            self.assertEqual(data["email"], "alex.chen@student.signal.dev")

            # Re-fetch returns the same user
            resp2 = await client.get("/api/v1/users/active")
            self.assertEqual(resp2.status_code, 200)
            self.assertEqual(resp2.json()["id"], data["id"])

    async def test_save_and_follow_interactions(self):
        async with AsyncClient(transport=self.transport, base_url="http://test") as client:
            # 1. Bootstrap user
            u_resp = await client.get("/api/v1/users/active")
            user_id = u_resp.json()["id"]

            # 2. Initially no interactions
            int_resp = await client.get(f"/api/v1/users/{user_id}/interactions")
            self.assertEqual(int_resp.status_code, 200)
            self.assertEqual(int_resp.json()["saved_opportunity_ids"], [])
            self.assertEqual(int_resp.json()["followed_opportunity_ids"], [])

            # 3. Save opportunity
            save_resp = await client.post(f"/api/v1/users/{user_id}/opportunities/{self.opp_id}/save")
            self.assertEqual(save_resp.status_code, 200)
            self.assertTrue(save_resp.json()["is_saved"])

            # 4. Check interactions
            int_resp2 = await client.get(f"/api/v1/users/{user_id}/interactions")
            self.assertIn(self.opp_id, int_resp2.json()["saved_opportunity_ids"])

            # 5. List saved opportunities
            saved_list = await client.get(f"/api/v1/users/{user_id}/saved")
            self.assertEqual(saved_list.status_code, 200)
            self.assertEqual(saved_list.json()["total"], 1)
            self.assertEqual(saved_list.json()["items"][0]["id"], self.opp_id)

            # 6. Follow opportunity
            follow_resp = await client.post(f"/api/v1/users/{user_id}/opportunities/{self.opp_id}/follow")
            self.assertEqual(follow_resp.status_code, 200)
            self.assertTrue(follow_resp.json()["is_followed"])

            followed_list = await client.get(f"/api/v1/users/{user_id}/followed")
            self.assertEqual(followed_list.status_code, 200)
            self.assertEqual(followed_list.json()["total"], 1)

            # 7. Unsave opportunity
            unsave_resp = await client.delete(f"/api/v1/users/{user_id}/opportunities/{self.opp_id}/save")
            self.assertEqual(unsave_resp.status_code, 200)
            self.assertFalse(unsave_resp.json()["is_saved"])

            # 8. Saved list is now 0
            saved_list2 = await client.get(f"/api/v1/users/{user_id}/saved")
            self.assertEqual(saved_list2.json()["total"], 0)

    async def test_dashboard_overview_aggregation(self):
        async with AsyncClient(transport=self.transport, base_url="http://test") as client:
            # Bootstrap user first
            u_resp = await client.get("/api/v1/users/active")
            user_id = u_resp.json()["id"]

            resp = await client.get(f"/api/v1/dashboard/overview?user_id={user_id}")
            self.assertEqual(resp.status_code, 200)
            data = resp.json()

            # Check stats
            self.assertIn("stats", data)
            self.assertGreaterEqual(data["stats"]["opportunities_tracked"], 1)

            # Check top priority
            self.assertIsNotNone(data["top_priority"])
            self.assertEqual(data["top_priority"]["opportunity"]["id"], self.opp_id)

            # Check deadlines approaching
            self.assertGreaterEqual(len(data["deadlines_approaching"]), 1)
            self.assertEqual(data["deadlines_approaching"][0]["opportunity_id"], self.opp_id)

            # Check for_you feed
            self.assertGreaterEqual(len(data["for_you"]), 1)
            self.assertEqual(data["for_you"][0]["opportunity"]["id"], self.opp_id)

            # Check recent announcements
            self.assertGreaterEqual(len(data["recent_announcements"]), 1)
