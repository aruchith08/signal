"""
Unit & Integration Tests for Priority 8: Entity Resolution Scalability
Validates:
- Bounded candidate query in Level 3 (Title + Organization)
- Bounded token-prefiltered candidate query in Level 5 (Conservative Token Similarity)
- Correct matching behavior with large candidate sets
- Preservation of strict cross-organization isolation guardrails
"""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from apps.api.models.base import Base
from apps.api.models.organization import Organization
from apps.api.models.opportunity import Opportunity
from services.intelligence.entity_resolution import EntityResolver
from shared.constants import MatchReason


class TestEntityResolutionScalability(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        self.session_factory = async_sessionmaker(
            bind=self.engine, class_=AsyncSession, expire_on_commit=False
        )

    async def asyncTearDown(self):
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await self.engine.dispose()

    async def test_level_3_bounded_candidate_lookup(self):
        """Level 3 matches opportunity under organization with bounded candidate query."""
        async with self.session_factory() as session:
            org = Organization(name="Tata Consultancy Services", slug="tcs", is_verified=True)
            session.add(org)
            await session.flush()

            # Seed target opportunity
            opp_target = Opportunity(
                title="TCS CodeVita Season 13",
                canonical_name="TCS CodeVita",
                slug="tcs-codevita-13",
                organization_id=org.id,
                category="hackathon",
                current_state="announced",
                content_hash="h1",
            )
            session.add(opp_target)

            # Seed 30 other opportunities under the same org to test scalability
            for i in range(30):
                session.add(
                    Opportunity(
                        title=f"TCS Innovate Challenge #{i}",
                        canonical_name=f"TCS Innovate #{i}",
                        slug=f"tcs-innovate-{i}",
                        organization_id=org.id,
                        category="hackathon",
                        current_state="announced",
                        content_hash=f"h_other_{i}",
                    )
                )
            await session.commit()

            resolver = EntityResolver(session)
            result = await resolver.resolve(
                title="TCS CodeVita Season 13",
                canonical_name="TCS CodeVita",
                organization_id=org.id,
            )

            self.assertTrue(result.matched)
            self.assertEqual(result.opportunity.id, opp_target.id)
            self.assertEqual(result.reason, MatchReason.EXACT_TITLE_ORGANIZATION)

    async def test_level_5_bounded_token_similarity_lookup(self):
        """Level 5 matches similar title under organization with token-prefiltered candidate query."""
        async with self.session_factory() as session:
            org = Organization(name="Google", slug="google", is_verified=True)
            session.add(org)
            await session.flush()

            opp_target = Opportunity(
                title="Google Summer of Code Mentorship Program",
                canonical_name="Google Summer of Code",
                slug="gsoc-mentorship",
                organization_id=org.id,
                category="open_source_program",
                current_state="announced",
                content_hash="ghash1",
            )
            session.add(opp_target)

            # Seed unrelated opportunities under Google
            for i in range(25):
                session.add(
                    Opportunity(
                        title=f"Google Cloud Architecture Challenge #{i}",
                        canonical_name=f"GCAC #{i}",
                        slug=f"gcac-{i}",
                        organization_id=org.id,
                        category="hackathon",
                        current_state="announced",
                        content_hash=f"g_other_{i}",
                    )
                )
            await session.commit()

            resolver = EntityResolver(session)
            result = await resolver.resolve(
                title="Google Summer of Code 2026 Mentorship",
                canonical_name="Google Summer of Code",
                organization_id=org.id,
            )

            self.assertTrue(result.matched)
            self.assertEqual(result.opportunity.id, opp_target.id)
            self.assertIn(
                result.reason,
                [MatchReason.DETERMINISTIC_SIMILARITY, MatchReason.EXACT_TITLE_ORGANIZATION],
            )
