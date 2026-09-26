"""
Unit Tests for VerificationEngine
"""
import unittest
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from apps.api.models import Base, Opportunity, OpportunitySource, VerifiedField
from services.verification.engine import VerificationEngine
from shared.constants import VerificationStatus, FieldVerificationStatus


class TestVerificationEngine(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        self.session_factory = async_sessionmaker(bind=self.engine, class_=AsyncSession, expire_on_commit=False)

        async with self.session_factory() as session:
            opp = Opportunity(
                title="Smart India Hackathon 2026",
                canonical_name="SIH 2026",
                slug="sih-2026-test",
                category="hackathon",
                year=2026,
                verification_status=VerificationStatus.DISCOVERED.value,
            )
            session.add(opp)
            await session.commit()
            self.opp_id = opp.id

    async def asyncTearDown(self):
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await self.engine.dispose()

    async def test_official_source_consensus_dominance(self):
        async with self.session_factory() as session:
            engine = VerificationEngine(session)

            # 1. Non-official aggregator source reports first
            s1 = await engine.register_source_contribution(
                opportunity_id=self.opp_id,
                source_url="https://unstop.com/hackathons/sih-2026",
                canonical_url="https://unstop.com/hackathons/sih-2026",
                source_title="SIH 2026 on Unstop",
                contributed_fields=["deadline"],
            )
            self.assertFalse(s1.is_official_source)
            self.assertEqual(s1.trust_score, 0.80)

            f1 = await engine.verify_field(
                opportunity_id=self.opp_id,
                field_name="deadline",
                new_value="2026-09-25",
                source_is_official=False,
                source_trust=0.80,
            )
            self.assertEqual(f1.value, "2026-09-25")
            self.assertFalse(f1.official_confirmation)

            # 2. Official source reports authoritative deadline
            s2 = await engine.register_source_contribution(
                opportunity_id=self.opp_id,
                source_url="https://sih.gov.in",
                canonical_url="https://sih.gov.in",
                source_title="Smart India Hackathon Official",
                contributed_fields=["deadline"],
            )
            self.assertTrue(s2.is_official_source)
            self.assertEqual(s2.trust_score, 1.00)

            f2 = await engine.verify_field(
                opportunity_id=self.opp_id,
                field_name="deadline",
                new_value="2026-09-20",
                source_is_official=True,
                source_trust=1.00,
            )
            self.assertEqual(f2.value, "2026-09-20")
            self.assertTrue(f2.official_confirmation)
            self.assertEqual(f2.verification_status, FieldVerificationStatus.VERIFIED.value)

            # 3. Overall consensus evaluation
            res = await engine.evaluate_and_update_opportunity(self.opp_id)
            self.assertEqual(res.status, VerificationStatus.VERIFIED.value)
            self.assertTrue(res.official_source_present)
            self.assertEqual(res.source_count, 2)


if __name__ == "__main__":
    unittest.main()
