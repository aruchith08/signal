"""
Comprehensive Test Suite for SIGNAL Phase 1C-A: Program Watch Engine & Watch Registry
Tests:
- Exact Alias Matching
- Canonical Name Matching
- Exact Name Matching
- Weighted Keyword Matching
- False-Positive Guardrails (Generic keywords alone never match)
- Multiple Watch Matches per Discovery
- Inactive Watch Exclusion
- Idempotent Match Persistence (Duplicate match prevention)
- Source Association as Supporting Evidence
- Match Explainability (Level, Reason, Terms, Score)
- Ingestion Pipeline Integration (Watch match created, Opportunity created, non-watch opportunities continue)
- REST APIs (CRUD, filtering, matches listing)
Mock-safe, in-memory SQLite, 0 cloud AI dependencies.
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
from apps.api.models import Opportunity, Organization, Source
from apps.api.models.discovery import RawDiscovery
from apps.api.models.program_watch import (
    ProgramWatch,
    ProgramWatchAlias,
    ProgramWatchKeyword,
    ProgramWatchSource,
    ProgramWatchMatch,
)
from connectors.base_connector import RawItem
from services.ingestion.pipeline import IngestionPipeline
from services.watch.matcher import ProgramWatchMatcher, WatchMatchResult
from services.watch.scoring import WatchMatchScorer
from services.watch.engine import ProgramWatchEngine
from shared.constants import (
    WatchConfidence,
    WatchMatchLevel,
    WatchPriority,
    DiscoveryStatus,
)
from shared.utils import normalize_title


class TestWatchMatcherUnit(unittest.TestCase):
    """Unit tests for deterministic ProgramWatchMatcher logic."""

    def setUp(self):
        self.watch = ProgramWatch(
            id="watch-tcs",
            name="TCS CodeVita",
            canonical_name="tcs codevita",
            priority=WatchPriority.CRITICAL.value,
            is_active=True,
        )
        self.watch.aliases = [
            ProgramWatchAlias(
                id="alias-1",
                program_watch_id="watch-tcs",
                alias="CodeVita",
                normalized_alias="codevita",
            ),
            ProgramWatchAlias(
                id="alias-2",
                program_watch_id="watch-tcs",
                alias="TCS CodeVita",
                normalized_alias="tcs codevita",
            ),
        ]
        self.watch.keywords = [
            ProgramWatchKeyword(
                id="kw-1",
                program_watch_id="watch-tcs",
                keyword="CodeVita",
                normalized_keyword="codevita",
                weight=1.0,
                is_distinctive=True,
            ),
            ProgramWatchKeyword(
                id="kw-2",
                program_watch_id="watch-tcs",
                keyword="TCS",
                normalized_keyword="tcs",
                weight=0.4,
                is_distinctive=False,
            ),
            ProgramWatchKeyword(
                id="kw-3",
                program_watch_id="watch-tcs",
                keyword="Programming",
                normalized_keyword="programming",
                weight=0.3,
                is_distinctive=False,
            ),
            ProgramWatchKeyword(
                id="kw-4",
                program_watch_id="watch-tcs",
                keyword="Competition",
                normalized_keyword="competition",
                weight=0.3,
                is_distinctive=False,
            ),
        ]
        self.watch.sources = []

    def test_exact_alias_match(self):
        """Verify exact alias in title triggers EXACT_ALIAS match with 1.0 score."""
        disc = RawDiscovery(
            id="disc-1",
            raw_title="Registrations for CodeVita are now open",
            raw_content="TCS has announced the registration schedule for students worldwide.",
            canonical_url="https://codevita.tcs.com/register",
            content_hash="hash1",
        )
        result: WatchMatchResult = ProgramWatchMatcher.match(disc, self.watch)

        self.assertTrue(result.matched)
        self.assertEqual(result.match_level, WatchMatchLevel.EXACT_ALIAS)
        self.assertEqual(result.score, 1.0)
        self.assertIn("CodeVita", result.matched_terms)
        self.assertEqual(result.confidence, WatchConfidence.HIGH)
        self.assertIn("Exact alias 'CodeVita' found in title", result.match_reason)

    def test_exact_canonical_name_match(self):
        """Verify exact canonical name triggers high-confidence match."""
        disc = RawDiscovery(
            id="disc-2",
            raw_title="TCS CodeVita Season 13 Announcement",
            raw_content="Registration details for the international coding challenge.",
            canonical_url="https://tcs.com/codevita",
            content_hash="hash2",
        )
        # Remove aliases and set distinct name to isolate canonical name rule
        self.watch.aliases = []
        self.watch.name = "TCS Premier Flagship Contest"
        self.watch.canonical_name = "codevita"
        result: WatchMatchResult = ProgramWatchMatcher.match(disc, self.watch)

        self.assertTrue(result.matched)
        self.assertEqual(result.match_level, WatchMatchLevel.EXACT_CANONICAL_NAME)
        self.assertGreaterEqual(result.score, 0.95)
        self.assertEqual(result.confidence, WatchConfidence.HIGH)

    def test_exact_name_match(self):
        """Verify exact program name triggers EXACT_NAME match."""
        gsoc_watch = ProgramWatch(
            id="watch-gsoc",
            name="Google Summer of Code",
            canonical_name="gsoc",
            priority=WatchPriority.CRITICAL.value,
            is_active=True,
        )
        gsoc_watch.aliases = []
        gsoc_watch.keywords = []
        gsoc_watch.sources = []

        disc = RawDiscovery(
            id="disc-3",
            raw_title="Google Summer of Code 2026 Timeline Released",
            raw_content="Open source contributor program timeline and accepted organizations.",
            canonical_url="https://summerofcode.withgoogle.com",
            content_hash="hash3",
        )
        result: WatchMatchResult = ProgramWatchMatcher.match(disc, gsoc_watch)

        self.assertTrue(result.matched)
        self.assertEqual(result.match_level, WatchMatchLevel.EXACT_NAME)
        self.assertEqual(result.score, 0.95)
        self.assertIn("Google Summer of Code", result.matched_terms)

    def test_weighted_keyword_match(self):
        """Verify weighted keyword match when distinctive keyword is present."""
        self.watch.aliases = []
        disc = RawDiscovery(
            id="disc-4",
            raw_title="Campus hiring through CodeVita programming competition",
            raw_content="Students are invited to participate in the annual contest.",
            canonical_url="https://tcs.com/jobs",
            content_hash="hash4",
        )
        result: WatchMatchResult = ProgramWatchMatcher.match(disc, self.watch)

        self.assertTrue(result.matched)
        self.assertEqual(result.match_level, WatchMatchLevel.KEYWORD_COMBINATION)
        self.assertGreaterEqual(result.score, 0.60)
        self.assertIn("CodeVita", result.matched_terms)

    def test_generic_keyword_false_positive_guardrail(self):
        """
        CRITICAL GUARDRAIL TEST:
        Generic keywords alone ('programming', 'competition', 'tcs')
        must NOT trigger a match when the distinctive keyword ('CodeVita') is absent.
        """
        self.watch.aliases = []
        disc = RawDiscovery(
            id="disc-5",
            raw_title="TCS announces a new programming competition",
            raw_content="General software engineering contest for university students.",
            canonical_url="https://tcs.com/general-contest",
            content_hash="hash5",
        )
        result: WatchMatchResult = ProgramWatchMatcher.match(disc, self.watch)

        # MUST NOT MATCH!
        self.assertFalse(result.matched)
        self.assertLess(result.score, 0.60)
        self.assertEqual(result.confidence, WatchConfidence.LOW)
        self.assertIn("No distinctive alias", result.match_reason)

    def test_inactive_watch_never_matches(self):
        """Verify inactive watches never participate in matching."""
        self.watch.is_active = False
        disc = RawDiscovery(
            id="disc-6",
            raw_title="Registrations for CodeVita are now open",
            raw_content="TCS has announced the registration schedule.",
            canonical_url="https://codevita.tcs.com",
            content_hash="hash6",
        )
        result: WatchMatchResult = ProgramWatchMatcher.match(disc, self.watch)

        self.assertFalse(result.matched)
        self.assertEqual(result.score, 0.0)
        self.assertIn("inactive", result.match_reason)

    def test_source_association_as_supporting_evidence(self):
        """Source association alone cannot match, but acts as a bonus when combined with distinctive terms."""
        source_id = "src-official"
        self.watch.aliases = []
        self.watch.sources = [
            ProgramWatchSource(
                id="src-assoc-1",
                program_watch_id="watch-tcs",
                source_id=source_id,
                is_active=True,
            )
        ]

        # Case A: Generic keywords only from the official source -> STILL REJECTED (Guardrail)
        disc_generic = RawDiscovery(
            id="disc-7a",
            source_id=source_id,
            raw_title="Annual student programming competition",
            raw_content="Competition hosted on official portal.",
            canonical_url="https://tcs.com/portal",
            content_hash="hash7a",
        )
        res_a = ProgramWatchMatcher.match(disc_generic, self.watch)
        self.assertFalse(res_a.matched)

        # Case B: Distinctive keyword + Source association -> Strong match with source mentioned in reason
        disc_with_term = RawDiscovery(
            id="disc-7b",
            source_id=source_id,
            raw_title="CodeVita registration portal active",
            raw_content="Apply for the challenge.",
            canonical_url="https://tcs.com/codevita",
            content_hash="hash7b",
        )
        res_b = ProgramWatchMatcher.match(disc_with_term, self.watch)
        self.assertTrue(res_b.matched)
        self.assertIn("associated source", res_b.match_reason)


class TestProgramWatchAsync(unittest.IsolatedAsyncioTestCase):
    """Integration tests with in-memory database verifying Engine, Idempotency, and Pipeline."""

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

    async def test_multiple_watch_matches_and_idempotency(self):
        """
        Verify:
        1. One discovery can match multiple distinct watches (SIH and MoE).
        2. Repeated evaluation produces exactly 1 match record per watch (strict idempotency).
        """
        async with self.session_factory() as session:
            # Create Watch 1: Smart India Hackathon
            watch_sih = ProgramWatch(
                name="Smart India Hackathon",
                canonical_name="smart india hackathon",
                priority=WatchPriority.CRITICAL.value,
                is_active=True,
            )
            session.add(watch_sih)
            await session.flush()
            session.add(ProgramWatchAlias(
                program_watch_id=watch_sih.id, alias="SIH", normalized_alias="sih"
            ))

            # Create Watch 2: AICTE Programs
            watch_aicte = ProgramWatch(
                name="AICTE Student Initiatives",
                canonical_name="aicte student initiatives",
                priority=WatchPriority.HIGH.value,
                is_active=True,
            )
            session.add(watch_aicte)
            await session.flush()
            session.add(ProgramWatchAlias(
                program_watch_id=watch_aicte.id, alias="AICTE", normalized_alias="aicte"
            ))

            # Create Discovery matching BOTH
            disc = RawDiscovery(
                raw_title="AICTE announces SIH 2026 Problem Statements",
                raw_content="The Ministry of Education and AICTE have released challenge statements for SIH.",
                original_url="https://sih.gov.in/news",
                canonical_url="https://sih.gov.in/news",
                content_hash="sih_aicte_hash",
            )
            session.add(disc)
            await session.commit()

            watch_engine = ProgramWatchEngine(session)

            # First evaluation
            matches = await watch_engine.evaluate_discovery(disc)
            await session.commit()

            # Should have matched BOTH watches!
            self.assertEqual(len(matches), 2)
            matched_watch_ids = {m.program_watch_id for m in matches}
            self.assertEqual(matched_watch_ids, {watch_sih.id, watch_aicte.id})

            # Check DB count
            count_stmt = select(func.count(ProgramWatchMatch.id)).where(
                ProgramWatchMatch.raw_discovery_id == disc.id
            )
            total_matches = (await session.execute(count_stmt)).scalar_one()
            self.assertEqual(total_matches, 2)

            # Second evaluation (Repeated Poll / Idempotency verification)
            matches_repeat = await watch_engine.evaluate_discovery(disc)
            await session.commit()

            # DB count MUST strictly remain 2 (Zero duplicate rows created)
            total_matches_repeat = (await session.execute(count_stmt)).scalar_one()
            self.assertEqual(total_matches_repeat, 2)

    async def test_pipeline_integration_with_and_without_watches(self):
        """
        Verify:
        1. When an item matches a watch, both ProgramWatchMatch and canonical Opportunity are created.
        2. When an item matches NO watch, Opportunity and Lifecycle processing continues normally (non-blocking).
        """
        async with self.session_factory() as session:
            # Seed GSoC watch
            gsoc = ProgramWatch(
                name="Google Summer of Code",
                canonical_name="google summer of code",
                priority=WatchPriority.CRITICAL.value,
                is_active=True,
            )
            session.add(gsoc)
            await session.flush()
            session.add(ProgramWatchAlias(
                program_watch_id=gsoc.id, alias="GSoC", normalized_alias="gsoc"
            ))
            await session.commit()

            pipeline = IngestionPipeline(session)

            # Item 1: Watched Program (GSoC)
            item1 = RawItem(
                title="GSoC 2026 contributor registrations open",
                url="https://summerofcode.withgoogle.com/apply",
                content="Google Summer of Code registrations are now officially open for contributors worldwide.",
                source_name="Google Tech",
                source_identifier="gsoc-1",
            )
            opp1 = await pipeline.process_raw_item(item1)
            await session.commit()

            # Verify Opportunity created
            self.assertIsNotNone(opp1)
            self.assertIn("GSoC", opp1.title)

            # Verify Watch Match created
            match1 = (
                await session.execute(
                    select(ProgramWatchMatch).where(ProgramWatchMatch.program_watch_id == gsoc.id)
                )
            ).scalars().first()
            self.assertIsNotNone(match1)
            self.assertEqual(match1.match_level, WatchMatchLevel.EXACT_ALIAS.value)
            self.assertEqual(match1.match_score, 1.0)

            # Item 2: Unwatched Program (Local College Hackathon)
            item2 = RawItem(
                title="MIT HackFest 2026",
                url="https://mithackfest.edu/register",
                content="Annual university hackathon and coding competition with cash prizes.",
                source_name="MIT Portal",
                source_identifier="mit-1",
            )
            opp2 = await pipeline.process_raw_item(item2)
            await session.commit()

            # Verify Opportunity STILL CREATED (Watch engine did NOT block it!)
            self.assertIsNotNone(opp2)
            self.assertEqual(opp2.title, "MIT HackFest 2026")

            # Verify NO watch match was created for Item 2
            item2_disc = (
                await session.execute(
                    select(RawDiscovery).where(RawDiscovery.external_id == "mit-1")
                )
            ).scalars().first()
            matches2 = (
                await session.execute(
                    select(ProgramWatchMatch).where(ProgramWatchMatch.raw_discovery_id == item2_disc.id)
                )
            ).scalars().all()
            self.assertEqual(len(matches2), 0)

    async def test_api_program_watches_crud_and_filtering(self):
        """Verify REST API CRUD endpoints for Program Watches and Matches."""
        async with AsyncClient(transport=self.transport, base_url="http://test") as client:
            # 1. Create ProgramWatch via POST
            create_payload = {
                "name": "Flipkart GRiD",
                "canonical_name": "flipkart grid",
                "description": "Campus challenge for engineers",
                "priority": "critical",
                "is_active": True,
                "aliases": [{"alias": "Flipkart GRiD"}, {"alias": "GRiD 6.0"}],
                "keywords": [
                    {"keyword": "Flipkart GRiD", "weight": 1.0, "is_distinctive": True},
                    {"keyword": "Robotics", "weight": 0.4, "is_distinctive": False},
                ],
            }
            resp = await client.post("/api/v1/program-watches", json=create_payload)
            self.assertEqual(resp.status_code, 201)
            watch_data = resp.json()
            watch_id = watch_data["id"]
            self.assertEqual(watch_data["name"], "Flipkart GRiD")
            self.assertEqual(len(watch_data["aliases"]), 2)
            self.assertEqual(len(watch_data["keywords"]), 2)

            # 2. Get ProgramWatch detail
            detail_resp = await client.get(f"/api/v1/program-watches/{watch_id}")
            self.assertEqual(detail_resp.status_code, 200)
            self.assertEqual(detail_resp.json()["id"], watch_id)

            # 3. List with priority filter
            list_resp = await client.get("/api/v1/program-watches?priority=critical")
            self.assertEqual(list_resp.status_code, 200)
            data = list_resp.json()
            self.assertEqual(data["total"], 1)
            self.assertEqual(data["items"][0]["id"], watch_id)

            # 4. Patch: Disable watch
            patch_resp = await client.patch(
                f"/api/v1/program-watches/{watch_id}", json={"is_active": False}
            )
            self.assertEqual(patch_resp.status_code, 200)
            self.assertFalse(patch_resp.json()["is_active"])

            # 5. List with is_active=false
            inactive_resp = await client.get("/api/v1/program-watches?is_active=false")
            self.assertEqual(inactive_resp.status_code, 200)
            self.assertEqual(inactive_resp.json()["total"], 1)

            # 6. Get matches for watch (should be empty initially)
            matches_resp = await client.get(f"/api/v1/program-watches/{watch_id}/matches")
            self.assertEqual(matches_resp.status_code, 200)
            self.assertEqual(matches_resp.json()["total"], 0)


if __name__ == "__main__":
    unittest.main()
