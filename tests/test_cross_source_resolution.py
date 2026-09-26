"""
Unit Tests for CrossSourceResolver
"""
import unittest
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from apps.api.models import Base, Opportunity, Organization
from services.verification.cross_source_resolution import CrossSourceResolver
from shared.constants import OpportunityCategory, OpportunityStatus


class TestCrossSourceResolver(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        self.session_factory = async_sessionmaker(bind=self.engine, class_=AsyncSession, expire_on_commit=False)

        async with self.session_factory() as session:
            org = Organization(name="Tata Consultancy Services", slug="tcs", is_verified=True)
            session.add(org)
            await session.flush()
            self.org_id = org.id

            opp = Opportunity(
                title="TCS CodeVita Season 13",
                canonical_name="CodeVita",
                slug="tcs-codevita-season-13",
                organization_id=org.id,
                category=OpportunityCategory.COMPETITIVE_PROGRAMMING.value,
                year=2026,
                season="Season 13",
                application_url="https://codevita.tcs.com/register",
                status=OpportunityStatus.ACTIVE.value,
            )
            session.add(opp)
            await session.commit()
            self.opp_id = opp.id

    async def asyncTearDown(self):
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await self.engine.dispose()

    async def test_level_1_exact_url_match(self):
        async with self.session_factory() as session:
            resolver = CrossSourceResolver(session)
            res = await resolver.resolve(
                title="CodeVita Online Test",
                canonical_url="https://codevita.tcs.com/register?utm_source=unstop",
            )
            self.assertTrue(res.matched)
            self.assertEqual(res.confidence, 1.00)
            self.assertEqual(res.opportunity.id, self.opp_id)
            self.assertEqual(res.match_level, "LEVEL_1_EXACT_URL")

    async def test_level_1_exact_name_org_year_match(self):
        async with self.session_factory() as session:
            resolver = CrossSourceResolver(session)
            res = await resolver.resolve(
                title="TCS CodeVita Season 13",
                organization_id=self.org_id,
                year=2026,
            )
            self.assertTrue(res.matched)
            self.assertEqual(res.confidence, 0.98)
            self.assertEqual(res.opportunity.id, self.opp_id)

    async def test_level_2_strong_deterministic_token_match(self):
        async with self.session_factory() as session:
            resolver = CrossSourceResolver(session)
            res = await resolver.resolve(
                title="CodeVita Season 13 Registration",
                organization_id=self.org_id,
                year=2026,
            )
            self.assertTrue(res.matched)
            self.assertGreaterEqual(res.confidence, 0.90)
            self.assertEqual(res.match_level, "LEVEL_2_STRONG_DETERMINISTIC")

    async def test_guardrail_prevents_mismatched_year(self):
        async with self.session_factory() as session:
            resolver = CrossSourceResolver(session)
            res = await resolver.resolve(
                title="TCS CodeVita Season 13",
                organization_id=self.org_id,
                year=2025,
            )
            self.assertFalse(res.matched)

    async def test_guardrail_prevents_mismatched_organization(self):
        async with self.session_factory() as session:
            other_org = Organization(name="Infosys", slug="infosys", is_verified=True)
            session.add(other_org)
            await session.flush()

            resolver = CrossSourceResolver(session)
            res = await resolver.resolve(
                title="TCS CodeVita Season 13",
                organization_id=other_org.id,
                year=2026,
            )
            self.assertFalse(res.matched)


if __name__ == "__main__":
    unittest.main()
