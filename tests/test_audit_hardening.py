"""
Automated Verification of Phase 0.5 Hardening Improvements for SIGNAL
"""
import asyncio
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

# Add root directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select

from apps.api.models import Base, Source, Opportunity, Organization
from connectors.base_connector import RawItem, BaseConnector
from connectors.mock_connector import MockConnector
from services.ingestion.deduplication import Deduplicator
from services.ingestion.filter import FastFilter
from services.ingestion.pipeline import IngestionPipeline
from services.intelligence.base_provider import BaseAIProvider
from services.intelligence.models import (
    ClassificationResult,
    ExtractionResult,
    SummarizationResult,
)
from services.intelligence.router import AIRouter
from shared.constants import OpportunityCategory, OpportunityStatus, SourceType, TrustLevel
from shared.utils import compute_content_hash, canonicalize_url, normalize_content_for_hash


class SlowFailingAIProvider(BaseAIProvider):
    """Simulates a third-party AI provider that hangs / times out."""

    def __init__(self):
        super().__init__(name="slow_provider", default_timeout_seconds=0.1)

    async def is_available(self) -> bool:
        return True

    async def classify(self, content: str) -> ClassificationResult:
        await asyncio.sleep(0.5)  # Exceeds default_timeout_seconds (0.1s)
        return ClassificationResult(
            is_opportunity=True,
            category=OpportunityCategory.HACKATHON,
            confidence=0.9,
            reasoning="Slow response",
            provider=self.name,
        )

    async def extract(self, content: str) -> ExtractionResult:
        await asyncio.sleep(0.5)
        raise RuntimeError("Should have timed out")

    async def summarize(self, content: str) -> SummarizationResult:
        await asyncio.sleep(0.5)
        raise RuntimeError("Should have timed out")


class TestAuditHardening(unittest.IsolatedAsyncioTestCase):
    """Verifies that Phase 0.5 hardening improvements function correctly under stress."""

    async def asyncSetUp(self):
        self.engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
        self.session_factory = async_sessionmaker(
            bind=self.engine, class_=AsyncSession, expire_on_commit=False
        )
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def asyncTearDown(self):
        await self.engine.dispose()

    def test_content_normalization_stability(self):
        """Verify that benign formatting changes (CRLF, trailing spaces, extra empty lines) yield identical hash."""
        text_standard = "Line 1\nLine 2\n\nLine 3"
        text_crlf = "Line 1  \r\nLine 2\r\n\r\n\r\nLine 3   "
        text_padded = "  Line 1\nLine 2\n\n\nLine 3\n\n  "

        hash1 = compute_content_hash(text_standard)
        hash2 = compute_content_hash(text_crlf)
        hash3 = compute_content_hash(text_padded)

        self.assertEqual(hash1, hash2)
        self.assertEqual(hash2, hash3)

    def test_url_canonicalization(self):
        """Verify URL canonicalization strips tracking parameters, fragments, and trailing slashes."""
        raw_url = "https://unstop.com/competitions/flipkart-grid-6/?utm_source=telegram&ref=newsletter&fbclid=xyz#section-rules/"
        canonical = canonicalize_url(raw_url)
        self.assertEqual(canonical, "https://unstop.com/competitions/flipkart-grid-6")

        # Preserves non-tracking query parameters in deterministic order
        query_url = "https://example.com/contest?batch=2026&utm_campaign=campus&track=ai"
        canonical_query = canonicalize_url(query_url)
        self.assertEqual(canonical_query, "https://example.com/contest?batch=2026&track=ai")

    def test_fast_filter_false_negative_immunity(self):
        """Verify that all required real-world announcement phrases pass FastFilter."""
        ff = FastFilter()
        real_world_phrases = [
            "Applications are open for the national innovation challenge.",
            "Registrations are now live for the coding contest.",
            "Call for applications: summer research program 2026.",
            "Student challenge announced by Ministry of Education.",
            "Hackathon announced with industry cash prizes.",
            "Deadline extended for proposal submission.",
            "Entries invited for annual developer challenge.",
            "Nominations open for youth tech fellowship.",
            "Fellowship applications invited from final year B.Tech students.",
            "New hiring challenge for software engineering roles.",
        ]
        for phrase in real_world_phrases:
            is_candidate, matches, score = ff.evaluate("Opportunity Headline", phrase)
            self.assertTrue(
                is_candidate,
                f"FastFilter produced false negative on phrase: '{phrase}' (Matches: {matches})",
            )
            self.assertGreater(score, 0.0)

    async def test_ai_router_timeout_and_fallback(self):
        """Verify that AIRouter catches timeout on slow primary provider and cascades to fallback."""
        router = AIRouter(task_timeout_seconds=0.1)
        # Register the slow provider as primary
        router.register_provider(SlowFailingAIProvider())

        # Force classification routing to slow_provider
        from apps.api.config import settings
        original_routing = settings.AI_ROUTING_CLASSIFICATION
        try:
            settings.AI_ROUTING_CLASSIFICATION = "slow_provider"
            # slow_provider will time out after 0.1s; router must catch AITimeoutError and fall back to mock
            result = await router.classify("TCS CodeVita contest announcement")
            self.assertTrue(result.is_opportunity)
            # The fallback provider ('mock') should have completed the task
            self.assertEqual(result.provider, "mock")
        finally:
            settings.AI_ROUTING_CLASSIFICATION = original_routing

    async def test_repeated_ingestion_idempotency(self):
        """Verify repeated polling creates zero duplicate opportunities and causes zero constraint violations."""
        async with self.session_factory() as session:
            pipeline = IngestionPipeline(session)
            connector = MockConnector()

            # Poll 1
            first_run = await pipeline.process_connector(connector)
            self.assertGreaterEqual(len(first_run), 3)

            # Poll 2 (Repeated polling of same source)
            second_run = await pipeline.process_connector(connector)
            self.assertGreaterEqual(len(second_run), 3)

            # Total rows in DB should remain exactly 3
            stmt = select(Opportunity)
            total_in_db = (await session.execute(stmt)).scalars().all()
            self.assertEqual(len(total_in_db), 3)

    async def test_inactive_connector_skipped(self):
        """Verify that a connector with is_active=False is completely skipped."""
        async with self.session_factory() as session:
            pipeline = IngestionPipeline(session)
            inactive_connector = MockConnector(is_active=False)
            results = await pipeline.process_connector(inactive_connector)
            self.assertEqual(len(results), 0)

            # Confirm no rows created in DB
            stmt = select(Opportunity)
            total = len((await session.execute(stmt)).scalars().all())
            self.assertEqual(total, 0)

    async def test_source_operational_metrics_updated(self):
        """Verify that source operational metrics (last_polled_at, last_successful_check) are updated."""
        async with self.session_factory() as session:
            # Create a source record in DB matching the connector slug
            source = Source(
                name="Mock Announcements",
                slug="mock-announcements",
                category=OpportunityCategory.COMPETITIVE_PROGRAMMING.value,
                source_type=SourceType.PUBLIC_FEED.value,
                base_url="https://mock-sources.signal.internal",
                trust_level=TrustLevel.HIGH.value,
                failure_count=0,
            )
            session.add(source)
            await session.commit()

            pipeline = IngestionPipeline(session)
            connector = MockConnector(name="Mock Announcements")
            await pipeline.process_connector(connector)

            # Check that source operational metrics were updated
            await session.refresh(source)
            self.assertIsNotNone(source.last_polled_at)
            self.assertIsNotNone(source.last_successful_check)
            self.assertEqual(source.failure_count, 0)

    async def test_deduplicator_by_canonical_url_and_title(self):
        """Verify Deduplicator catches duplicates by canonical URL and title."""
        async with self.session_factory() as session:
            dedup = Deduplicator(session)

            # Create an opportunity with a canonical URL
            opp = Opportunity(
                title="Smart India Hackathon 2026",
                slug="sih-2026",
                category=OpportunityCategory.GOVERNMENT.value,
                application_url="https://sih.gov.in/portal",
                content_hash="unique_hash_999",
            )
            session.add(opp)
            await session.commit()

            # 1. Matches by URL with tracking junk
            duplicate_url = "https://sih.gov.in/portal/?utm_source=twitter&ref=share"
            match = await dedup.find_duplicate(raw_content="different text", application_url=duplicate_url)
            self.assertIsNotNone(match)
            self.assertEqual(match.id, opp.id)

            # 2. Matches by normalized title
            match_title = await dedup.find_duplicate(raw_content="diff text 2", title="Smart India Hackathon 2026")
            self.assertIsNotNone(match_title)
            self.assertEqual(match_title.id, opp.id)


if __name__ == "__main__":
    unittest.main()
