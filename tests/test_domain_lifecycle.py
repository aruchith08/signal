"""
Unit and Integration Tests for SIGNAL Phase 1B: Opportunity Intelligence & Lifecycle Engine
Validates:
- Content Classification (Opportunity, Event Update, Deadline Update, Result, Informational)
- Hierarchical Entity Resolution & False-Merge Prevention
- Opportunity Lifecycle & Chronological Event History
- Event Deduplication & Idempotency
- Informational Content Non-Opportunity Policy
- API Endpoints (Lifecycle history, filtering, discovery classification)
All tests are mock-safe (no external network or AI API dependencies).
"""
from datetime import datetime, timezone
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select, func

from apps.api.database import get_db, Base
from apps.api.main import app
from apps.api.models import Opportunity, OpportunityEvent, Organization, Source
from apps.api.models.alias import OpportunityAlias
from apps.api.models.discovery import RawDiscovery
from connectors.base_connector import RawItem
from services.ingestion.pipeline import IngestionPipeline
from services.intelligence.classifier import DomainClassifier
from services.intelligence.entity_resolution import EntityResolver
from services.lifecycle.engine import LifecycleEngine
from shared.constants import (
    ContentClassification,
    DiscoveryStatus,
    EventType,
    MatchReason,
    OpportunityCategory,
)


class TestDomainClassification(unittest.TestCase):
    """Verifies deterministic classification across various announcement archetypes."""

    def test_new_opportunity_classification(self):
        title = "TCS announces CodeVita Season 13"
        content = "Tata Consultancy Services announces TCS CodeVita Season 13 global coding challenge for students."
        u = DomainClassifier.classify(title, content, source_name="TCS Portal")

        self.assertEqual(u.classification, ContentClassification.OPPORTUNITY)
        self.assertEqual(u.lifecycle_event_type, EventType.ANNOUNCED)
        self.assertEqual(u.season, "13")
        self.assertTrue(u.is_actionable_opportunity)
        self.assertIn("CodeVita", u.canonical_name)

    def test_registration_open_update(self):
        title = "TCS CodeVita Season 13 registrations are open"
        content = "Registrations are now open for TCS CodeVita Season 13. Apply now on Campus Commune."
        u = DomainClassifier.classify(title, content, source_name="TCS Portal")

        self.assertEqual(u.classification, ContentClassification.EVENT_UPDATE)
        self.assertEqual(u.lifecycle_event_type, EventType.REGISTRATION_OPEN)
        self.assertTrue(u.is_actionable_opportunity)

    def test_deadline_extension_update(self):
        title = "CodeVita registration deadline extended"
        content = "The last date for TCS CodeVita Season 13 registrations has been extended till next Sunday."
        u = DomainClassifier.classify(title, content, source_name="TCS Portal")

        self.assertEqual(u.classification, ContentClassification.DEADLINE_UPDATE)
        self.assertEqual(u.lifecycle_event_type, EventType.DEADLINE_EXTENDED)
        self.assertTrue(u.is_actionable_opportunity)

    def test_result_announcement(self):
        title = "Smart India Hackathon 2026 winners declared"
        content = "Ministry of Education announces the winners and merit list for SIH 2026 Grand Finale."
        u = DomainClassifier.classify(title, content, source_name="SIH Portal")

        self.assertEqual(u.classification, ContentClassification.RESULT)
        self.assertEqual(u.lifecycle_event_type, EventType.RESULTS_ANNOUNCED)
        self.assertTrue(u.is_actionable_opportunity)

    def test_informational_article_rejected_from_opportunities(self):
        title = "GitHub availability report: August 2026"
        content = "In August 2026, we experienced 3 minor incidents affecting Git operations and Actions."
        u = DomainClassifier.classify(title, content, source_name="GitHub Blog")

        self.assertEqual(u.classification, ContentClassification.INFORMATIONAL)
        self.assertFalse(u.is_actionable_opportunity)

    def test_general_tech_article_informational(self):
        title = "Decoding the new AI lingo: Loops, harnesses, squads, hill climbing"
        content = "A guide to the latest buzzwords and concepts emerging in generative AI workflows."
        u = DomainClassifier.classify(title, content, source_name="GitHub Blog")

        self.assertEqual(u.classification, ContentClassification.INFORMATIONAL)
        self.assertFalse(u.is_actionable_opportunity)


class TestEntityResolutionAndGuardrails(unittest.IsolatedAsyncioTestCase):
    """Verifies multi-tiered entity resolution and false-merge guardrails."""

    async def asyncSetUp(self):
        self.engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
        self.session_factory = async_sessionmaker(
            bind=self.engine, class_=AsyncSession, expire_on_commit=False
        )
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def asyncTearDown(self):
        await self.engine.dispose()

    async def test_exact_url_and_title_org_matching(self):
        async with self.session_factory() as session:
            org = Organization(name="TCS", slug="tcs")
            session.add(org)
            await session.flush()

            opp = Opportunity(
                title="TCS CodeVita Season 13",
                canonical_name="TCS CodeVita",
                slug="tcs-codevita-season-13",
                organization_id=org.id,
                category=OpportunityCategory.COMPETITIVE_PROGRAMMING.value,
                application_url="https://codevita.tcs.com",
                year=2026,
                season="13",
            )
            session.add(opp)
            await session.commit()

            resolver = EntityResolver(session)

            # Test Level 2: URL match
            res_url = await resolver.resolve(
                title="CodeVita Challenge",
                canonical_url="https://codevita.tcs.com?utm_source=twitter",
            )
            self.assertTrue(res_url.matched)
            self.assertEqual(res_url.reason, MatchReason.CANONICAL_URL)
            self.assertEqual(res_url.opportunity.id, opp.id)

            # Test Level 3: Exact Title + Organization
            res_title = await resolver.resolve(
                title="TCS CodeVita Season 13",
                organization_id=org.id,
            )
            self.assertTrue(res_title.matched)
            self.assertEqual(res_title.reason, MatchReason.EXACT_TITLE_ORGANIZATION)

    async def test_alias_matching(self):
        async with self.session_factory() as session:
            opp = Opportunity(
                title="Google Summer of Code 2026",
                canonical_name="Google Summer of Code",
                slug="gsoc-2026",
                category=OpportunityCategory.OPEN_SOURCE_PROGRAM.value,
            )
            session.add(opp)
            await session.flush()

            alias = OpportunityAlias(opportunity_id=opp.id, alias="GSoC 2026")
            session.add(alias)
            await session.commit()

            resolver = EntityResolver(session)
            res = await resolver.resolve(title="GSoC 2026")
            self.assertTrue(res.matched)
            self.assertEqual(res.reason, MatchReason.ALIAS)
            self.assertEqual(res.opportunity.id, opp.id)

    async def test_false_merge_prevention_across_different_orgs(self):
        """Ensure identical titles from different organizations are NEVER merged."""
        async with self.session_factory() as session:
            org_msft = Organization(name="Microsoft", slug="microsoft")
            org_goog = Organization(name="Google", slug="google")
            session.add_all([org_msft, org_goog])
            await session.flush()

            opp = Opportunity(
                title="AI Student Hackathon 2026",
                slug="ai-student-hackathon-msft",
                organization_id=org_msft.id,
                year=2026,
            )
            session.add(opp)
            await session.commit()

            resolver = EntityResolver(session)
            # Query same title but under Google
            res = await resolver.resolve(
                title="AI Student Hackathon 2026",
                organization_id=org_goog.id,
                year=2026,
            )
            self.assertFalse(res.matched)
            self.assertEqual(res.reason, MatchReason.NEW_ENTITY)

    async def test_false_merge_prevention_across_conflicting_years(self):
        """Ensure opportunities from different years are NEVER merged."""
        async with self.session_factory() as session:
            org = Organization(name="MoE", slug="moe")
            session.add(org)
            await session.flush()

            opp = Opportunity(
                title="Smart India Hackathon",
                slug="sih-2025",
                organization_id=org.id,
                year=2025,
            )
            session.add(opp)
            await session.commit()

            resolver = EntityResolver(session)
            # Query candidate for 2026
            res = await resolver.resolve(
                title="Smart India Hackathon",
                organization_id=org.id,
                year=2026,
            )
            self.assertFalse(res.matched)
            self.assertEqual(res.reason, MatchReason.NEW_ENTITY)


class TestLifecycleProgressionAndIdempotency(unittest.IsolatedAsyncioTestCase):
    """Verifies end-to-end multi-stage opportunity lifecycle tracking and event idempotency."""

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

    async def asyncTearDown(self):
        app.dependency_overrides.clear()
        await self.engine.dispose()

    async def test_full_opportunity_lifecycle_progression(self):
        """
        Simulates:
        1. TCS announces CodeVita Season 13 (New Opportunity + ANNOUNCED event)
        2. Registrations open (Updates existing Opportunity + REGISTRATION_OPEN event)
        3. Deadline extended (Updates existing Opportunity + DEADLINE_EXTENDED event)
        4. Repeated poll of deadline announcement (Idempotent: 0 new opps, 0 duplicate events)
        """
        async with self.session_factory() as session:
            pipeline = IngestionPipeline(session)

            # Stage 1: Initial Announcement
            item1 = RawItem(
                title="TCS announces CodeVita Season 13",
                url="https://codevita.tcs.com/announcement",
                content="TCS announces CodeVita Season 13 global contest for engineering students.",
                source_name="TCS Portal",
                source_identifier="tcs-1",
                metadata={"organization": "TCS"},
            )
            opp1 = await pipeline.process_raw_item(item1)
            self.assertIsNotNone(opp1)
            opp_id = opp1.id

            # Verify 1 opportunity in DB
            total_opps = (await session.execute(select(func.count(Opportunity.id)))).scalar_one()
            self.assertEqual(total_opps, 1)

            # Verify 1 event (ANNOUNCED)
            events = (await session.execute(select(OpportunityEvent).where(OpportunityEvent.opportunity_id == opp_id))).scalars().all()
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0].event_type, EventType.ANNOUNCED.value)

            # Stage 2: Registration Open
            item2 = RawItem(
                title="TCS CodeVita Season 13 registrations are open",
                url="https://codevita.tcs.com/register",
                content="Registrations are now open for TCS CodeVita Season 13 on the Campus Commune platform.",
                source_name="TCS Portal",
                source_identifier="tcs-2",
                metadata={"organization": "TCS"},
            )
            opp2 = await pipeline.process_raw_item(item2)
            self.assertEqual(opp2.id, opp_id)  # Matched existing!
            self.assertEqual(opp2.current_state, EventType.REGISTRATION_OPEN.value)

            # Total opportunities remains 1
            total_opps = (await session.execute(select(func.count(Opportunity.id)))).scalar_one()
            self.assertEqual(total_opps, 1)

            # Events now contains 2 events
            events = (await session.execute(
                select(OpportunityEvent).where(OpportunityEvent.opportunity_id == opp_id).order_by(OpportunityEvent.created_at.asc())
            )).scalars().all()
            self.assertEqual(len(events), 2)
            self.assertEqual(events[1].event_type, EventType.REGISTRATION_OPEN.value)

            # Stage 3: Deadline Extended
            item3 = RawItem(
                title="CodeVita registration deadline extended",
                url="https://codevita.tcs.com/deadline-extension",
                content="TCS CodeVita Season 13 registration deadline extended till October 31.",
                source_name="TCS Portal",
                source_identifier="tcs-3",
                metadata={"organization": "TCS"},
            )
            opp3 = await pipeline.process_raw_item(item3)
            self.assertEqual(opp3.id, opp_id)
            self.assertEqual(opp3.current_state, EventType.DEADLINE_EXTENDED.value)

            # Events now contains 3 events
            events = (await session.execute(
                select(OpportunityEvent).where(OpportunityEvent.opportunity_id == opp_id).order_by(OpportunityEvent.created_at.asc())
            )).scalars().all()
            self.assertEqual(len(events), 3)
            self.assertEqual(events[2].event_type, EventType.DEADLINE_EXTENDED.value)
            self.assertTrue(events[2].is_critical)

            # Stage 4: Repeated Poll (Idempotency verification)
            opp3_repeat = await pipeline.process_raw_item(item3)
            self.assertEqual(opp3_repeat.id, opp_id)

            # Events count MUST remain strictly 3 (no duplicate events created)
            events = (await session.execute(
                select(OpportunityEvent).where(OpportunityEvent.opportunity_id == opp_id)
            )).scalars().all()
            self.assertEqual(len(events), 3)

    async def test_informational_content_audited_without_creating_opportunity(self):
        """Verifies that informational tech articles are audited in RawDiscovery without creating Opportunity."""
        async with self.session_factory() as session:
            pipeline = IngestionPipeline(session)

            info_item = RawItem(
                title="GitHub availability report: August 2026",
                url="https://github.blog/news/availability-aug-2026",
                content="Our system availability and incident analysis for the month of August.",
                source_name="GitHub Blog",
                source_identifier="gh-info-1",
            )
            opp = await pipeline.process_raw_item(info_item)
            self.assertIsNone(opp)

            # Zero opportunities in DB
            total_opps = (await session.execute(select(func.count(Opportunity.id)))).scalar_one()
            self.assertEqual(total_opps, 0)

            # 1 Discovery record exists with classification="informational" and status="filtered_out"
            disc = (await session.execute(select(RawDiscovery))).scalars().first()
            self.assertIsNotNone(disc)
            self.assertEqual(disc.content_classification, ContentClassification.INFORMATIONAL.value)
            self.assertEqual(disc.status, DiscoveryStatus.FILTERED_OUT.value)
            self.assertIsNone(disc.opportunity_id)

    async def test_api_opportunity_lifecycle_endpoints(self):
        """Verifies GET /api/v1/opportunities/{id}/events and filtering."""
        async with self.session_factory() as session:
            pipeline = IngestionPipeline(session)

            # Ingest initial announcement
            item = RawItem(
                title="TCS announces CodeVita Season 13",
                url="https://codevita.tcs.com/announcement",
                content="TCS announces CodeVita Season 13 coding competition.",
                source_name="TCS Portal",
                source_identifier="tcs-api-1",
                metadata={"organization": "TCS"},
            )
            opp = await pipeline.process_raw_item(item)
            opp_id = opp.id

            # Add registration open update
            item2 = RawItem(
                title="TCS CodeVita Season 13 registrations are open",
                url="https://codevita.tcs.com/register",
                content="Registrations are now open for TCS CodeVita Season 13.",
                source_name="TCS Portal",
                source_identifier="tcs-api-2",
                metadata={"organization": "TCS"},
            )
            await pipeline.process_raw_item(item2)
            await session.commit()

        # Call API through test client
        async with AsyncClient(transport=self.transport, base_url="http://test") as client:
            # Test event history endpoint
            resp = await client.get(f"/api/v1/opportunities/{opp_id}/events")
            self.assertEqual(resp.status_code, 200)
            events = resp.json()
            self.assertEqual(len(events), 2)
            event_types = [e["event_type"] for e in events]
            self.assertIn("announced", event_types)
            self.assertIn("registration_open", event_types)

            # Test filtering by current_state
            state_resp = await client.get("/api/v1/opportunities?current_state=registration_open")
            self.assertEqual(state_resp.status_code, 200)
            data = state_resp.json()
            self.assertEqual(data["total"], 1)
            self.assertEqual(data["items"][0]["id"], opp_id)


if __name__ == "__main__":
    unittest.main()
