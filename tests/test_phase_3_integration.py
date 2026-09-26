"""
End-to-End Integration Tests for Phase 3
Tests multi-source ingestion, fact verification, conflict recording, and REST APIs.
"""
import unittest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from apps.api.database import Base, get_db
from apps.api.main import app
from apps.api.models import Opportunity, Organization, Source
from services.verification.engine import VerificationEngine
from shared.constants import VerificationStatus, FieldVerificationStatus, ConflictStatus


class TestPhase3Integration(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        self.session_factory = async_sessionmaker(bind=self.engine, class_=AsyncSession, expire_on_commit=False)

        async def override_get_db():
            async with self.session_factory() as session:
                yield session

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

        # Seed initial canonical opportunity
        async with self.session_factory() as session:
            org = Organization(name="Tata Consultancy Services", slug="tcs", is_verified=True)
            session.add(org)
            await session.flush()

            opp = Opportunity(
                title="TCS CodeVita Season 13",
                canonical_name="CodeVita",
                slug="tcs-codevita-season-13-test",
                organization_id=org.id,
                year=2026,
                season="Season 13",
                category="competitive_programming",
                application_url="https://codevita.tcs.com",
                verification_status=VerificationStatus.DISCOVERED.value,
            )
            session.add(opp)
            await session.commit()
            self.opp_id = opp.id

    async def asyncTearDown(self):
        app.dependency_overrides.clear()
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await self.engine.dispose()

    async def test_multi_source_consensus_and_api(self):
        async with self.session_factory() as session:
            engine = VerificationEngine(session)

            # 1. Official Source Contributes
            await engine.register_source_contribution(
                opportunity_id=self.opp_id,
                source_url="https://codevita.tcs.com/apply",
                canonical_url="https://codevita.tcs.com/apply",
                source_title="Official CodeVita Portal",
                contributed_fields=["title", "deadline", "application_url"],
            )
            await engine.verify_field(
                opportunity_id=self.opp_id,
                field_name="deadline",
                new_value="2026-09-20",
                source_is_official=True,
                source_trust=0.95,
            )

            # 2. Aggregator Source Contributes Conflicting Deadline
            await engine.register_source_contribution(
                opportunity_id=self.opp_id,
                source_url="https://unstop.com/competitions/tcs-codevita",
                canonical_url="https://unstop.com/competitions/tcs-codevita",
                source_title="Unstop CodeVita Listing",
                contributed_fields=["deadline"],
            )
            await engine.verify_field(
                opportunity_id=self.opp_id,
                field_name="deadline",
                new_value="2026-09-25",
                source_is_official=False,
                source_trust=0.80,
            )

            # Evaluate with incoming conflict
            incoming_data = {"deadline_date": "2026-09-25"}
            incoming_source_info = {"source_name": "unstop", "trust_score": 0.80}
            await engine.evaluate_and_update_opportunity(
                opportunity_id=self.opp_id,
                incoming_data=incoming_data,
                incoming_source_info=incoming_source_info,
            )
            await session.commit()

        # 3. Test REST APIs
        # Verification Overview
        res = self.client.get(f"/api/v1/opportunities/{self.opp_id}/verification")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["opportunity_id"], self.opp_id)
        self.assertEqual(data["source_count"], 2)
        self.assertTrue(data["official_source_present"])
        self.assertEqual(len(data["sources"]), 2)
        self.assertEqual(len(data["conflicts"]), 1)
        self.assertEqual(data["conflicts"][0]["field_name"], "deadline")

        # Contributing Sources API
        src_res = self.client.get(f"/api/v1/opportunities/{self.opp_id}/sources")
        self.assertEqual(src_res.status_code, 200)
        self.assertEqual(len(src_res.json()), 2)

        # Conflicts Query API
        conf_res = self.client.get(f"/api/v1/verification/conflicts?opportunity_id={self.opp_id}")
        self.assertEqual(conf_res.status_code, 200)
        self.assertEqual(len(conf_res.json()), 1)


if __name__ == "__main__":
    unittest.main()
