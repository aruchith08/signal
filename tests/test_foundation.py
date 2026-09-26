"""
Automated Verification Test Suite for SIGNAL Phase 0 Foundation
"""
import asyncio
import sys
import unittest
from datetime import datetime, timezone

# Add root directory to sys.path
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.constants import (
    OpportunityCategory,
    OpportunityStatus,
    VerificationStatus,
    EventType,
    TrustLevel,
    PriorityLevel,
)
from shared.utils import slugify, compute_content_hash
from services.ingestion.filter import FastFilter
from services.intelligence.router import AIRouter
from services.intelligence.providers.mock_provider import MockAIProvider
from connectors.mock_connector import MockConnector
from services.notifications.mock_notifier import MockNotifier

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from apps.api.models import Base, Organization, Source, Opportunity, OpportunityEvent
from services.ingestion.pipeline import IngestionPipeline


class TestSignalFoundation(unittest.IsolatedAsyncioTestCase):
    """Verifies core architectural components of SIGNAL Phase 0."""

    async def asyncSetUp(self):
        # Create an in-memory SQLite async engine for isolated testing
        self.engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
        self.session_factory = async_sessionmaker(
            bind=self.engine, class_=AsyncSession, expire_on_commit=False
        )
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def asyncTearDown(self):
        await self.engine.dispose()

    def test_shared_utilities(self):
        """Verify slugification and content hashing."""
        slug = slugify("TCS CodeVita Season 12 (Global)!")
        self.assertEqual(slug, "tcs-codevita-season-12-global")

        hash1 = compute_content_hash("Sample announcement text")
        hash2 = compute_content_hash("Sample announcement text")
        hash3 = compute_content_hash("Different announcement text")
        self.assertEqual(hash1, hash2)
        self.assertNotEqual(hash1, hash3)

    def test_fast_filter(self):
        """Verify deterministic keyword & negative pattern pre-filter."""
        ff = FastFilter()
        # Positive case
        is_candidate, matches, score = ff.evaluate(
            "New Hackathon Announcement",
            "Registrations are open for the annual coding competition with cash prizes.",
        )
        self.assertTrue(is_candidate)
        self.assertGreater(score, 0.0)
        self.assertTrue(any("hackathon" in m or "registr" in m for m in matches))

        # Negative case (disqualified by sports pattern)
        is_candidate, _, _ = ff.evaluate(
            "Live Football Score",
            "Full time football score match report and highlights.",
        )
        self.assertFalse(is_candidate)

    async def test_ai_router_and_mock_provider(self):
        """Verify AI Gateway task routing to MockAIProvider."""
        router = AIRouter()
        sample_text = "TCS CodeVita Season 12 coding contest registration deadline announcement."

        # 1. Classification
        classification = await router.classify(sample_text)
        self.assertTrue(classification.is_opportunity)
        self.assertEqual(classification.category, OpportunityCategory.COMPETITIVE_PROGRAMMING)
        self.assertGreaterEqual(classification.confidence, 0.5)

        # 2. Extraction
        extraction = await router.extract(sample_text)
        self.assertIn("TCS", extraction.title)
        self.assertEqual(extraction.category, OpportunityCategory.COMPETITIVE_PROGRAMMING)
        self.assertGreater(len(extraction.events), 0)

        # 3. Summarization
        summary = await router.summarize(sample_text)
        self.assertTrue(len(summary.summary) > 0)
        self.assertTrue(len(summary.key_highlights) > 0)

    async def test_mock_connector(self):
        """Verify connector yields properly formatted RawItem instances."""
        connector = MockConnector()
        self.assertTrue(await connector.health_check())
        raw_items = await connector.fetch_raw_items()
        self.assertGreaterEqual(len(raw_items), 3)
        self.assertTrue(any("CodeVita" in item.title for item in raw_items))

    async def test_database_models_and_relationships(self):
        """Verify SQLAlchemy ORM models, foreign keys, and relations."""
        async with self.session_factory() as session:
            # Create Organization
            org = Organization(
                name="Tata Consultancy Services",
                slug="tcs",
                website="https://www.tcs.com",
                is_verified=True,
            )
            session.add(org)
            await session.flush()

            # Create Source
            source = Source(
                name="TCS Campus Portal",
                slug="tcs-campus",
                organization_id=org.id,
                category=OpportunityCategory.COMPETITIVE_PROGRAMMING.value,
                base_url="https://campus.tcs.com",
                trust_level=TrustLevel.HIGHEST.value,
            )
            session.add(source)
            await session.flush()

            # Create Opportunity
            opp = Opportunity(
                title="TCS CodeVita S12",
                slug="tcs-codevita-s12",
                organization_id=org.id,
                source_id=source.id,
                category=OpportunityCategory.COMPETITIVE_PROGRAMMING.value,
                status=OpportunityStatus.ACTIVE.value,
                verification_status=VerificationStatus.VERIFIED.value,
                confidence_score=95,
                official=True,
                content_hash="mock_hash_12345",
            )
            session.add(opp)
            await session.flush()

            # Create Event
            event = OpportunityEvent(
                opportunity_id=opp.id,
                event_type=EventType.REGISTRATION_CLOSING.value,
                title="CodeVita Registration Closes",
                deadline_date=datetime.now(timezone.utc),
                is_critical=True,
            )
            session.add(event)
            await session.commit()

            # Query and verify relationships
            stmt = (
                select(Opportunity)
                .options(
                    selectinload(Opportunity.organization),
                    selectinload(Opportunity.source),
                    selectinload(Opportunity.events),
                )
                .where(Opportunity.id == opp.id)
            )
            loaded_opp = (await session.execute(stmt)).scalars().first()
            self.assertIsNotNone(loaded_opp)
            self.assertEqual(loaded_opp.organization.name, "Tata Consultancy Services")
            self.assertEqual(loaded_opp.source.name, "TCS Campus Portal")
            self.assertEqual(len(loaded_opp.events), 1)
            self.assertTrue(loaded_opp.events[0].is_critical)

    async def test_ingestion_pipeline_end_to_end(self):
        """Verify the full IngestionPipeline end-to-end with MockConnector."""
        async with self.session_factory() as session:
            pipeline = IngestionPipeline(session)
            connector = MockConnector()
            opportunities = await pipeline.process_connector(connector)
            self.assertEqual(len(opportunities), 3)

            # Test deduplication on re-running same connector
            dupes = await pipeline.process_connector(connector)
            # Re-run should return the existing opportunities without duplicate row inserts
            stmt = select(Opportunity)
            total_count = len((await session.execute(stmt)).scalars().all())
            self.assertEqual(total_count, 3)

    async def test_mock_notifier(self):
        """Verify notification dispatcher records messages."""
        notifier = MockNotifier()
        success = await notifier.send(
            recipient="user_chat_123",
            message="Test critical alert: TCS CodeVita deadline in 24 hours!",
            priority=PriorityLevel.CRITICAL,
        )
        self.assertTrue(success)
        self.assertEqual(len(notifier.sent_messages), 1)
        self.assertEqual(notifier.sent_messages[0]["priority"], "critical")


if __name__ == "__main__":
    unittest.main()
