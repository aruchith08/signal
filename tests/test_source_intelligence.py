"""
SIGNAL 📡 — Phase 1C: Source Intelligence, Change Detection & Health Test Suite
Validates SourceRegistry, SourceSnapshot, MeaningfulChangeDetector, DateExtractor,
DeadlineEvaluator, OrganizationAlias resolution, Connector contracts, and Dashboard REST APIs.
"""
from datetime import datetime, timezone
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from apps.api.database import Base
from apps.api.main import app
from apps.api.models.organization import Organization
from apps.api.models.organization_alias import OrganizationAlias
from apps.api.models.source import Source
from apps.api.models.snapshot import SourceSnapshot
from connectors.competitive_programming.codechef import CodeChefConnector
from connectors.competitive_programming.hackerrank import HackerRankConnector
from connectors.competitive_programming.leetcode import LeetCodeConnector
from connectors.open_source.gsoc import GSoCConnector
from connectors.government.mygov import MyGovConnector
from connectors.hackathons.mlh import MLHConnector
from services.ingestion.change_detection import MeaningfulChangeDetector, SnapshotManager
from services.ingestion.pipeline import IngestionPipeline
from services.intelligence.date_extraction import DateExtractor, DeadlineEvaluator
from services.lifecycle.engine import LifecycleEngine
from services.sources.registry import SourceDefinition, SourceRegistry, source_registry
from shared.constants import (
    ChangeType,
    EventType,
    OpportunityCategory,
    PollingPolicy,
    PriorityLevel,
    SourceHealthStatus,
    SourceType,
    TrustLevel,
)
from tests.helpers.connector_contract import ConnectorContractTestMixin


class TestSourceRegistryAndUnit(unittest.TestCase, ConnectorContractTestMixin):
    """Fast unit tests for SourceRegistry, DateExtractor, ChangeDetector, and Connector normalization."""

    # =========================================================================
    # PART 1: Source Registry Tests
    # =========================================================================
    def test_source_registry_catalog(self):
        """Test catalog lookup, filtering, and connector instantiation."""
        codeforces = source_registry.get("codeforces")
        self.assertIsNotNone(codeforces)
        self.assertEqual(codeforces.organization_slug, "codeforces")
        self.assertEqual(codeforces.priority, PriorityLevel.HIGH)

        cp_sources = source_registry.list_sources(category=OpportunityCategory.COMPETITIVE_PROGRAMMING)
        self.assertGreaterEqual(len(cp_sources), 4)
        slugs = [s.slug for s in cp_sources]
        self.assertIn("codeforces", slugs)
        self.assertIn("codechef", slugs)
        self.assertIn("hackerrank", slugs)
        self.assertIn("leetcode", slugs)

        critical_sources = source_registry.list_sources(priority=PriorityLevel.CRITICAL)
        crit_slugs = [s.slug for s in critical_sources]
        self.assertIn("smart-india-hackathon", crit_slugs)
        self.assertIn("gsoc", crit_slugs)

        connector = source_registry.get_connector("codechef")
        self.assertIsInstance(connector, CodeChefConnector)
        self.assertEqual(connector.name, "CodeChef")

    # =========================================================================
    # PART 2: Date Extraction & Deadline Intelligence Tests
    # =========================================================================
    def test_date_extraction_formats(self):
        """Test robust parsing of multiple real-world date formats."""
        texts = [
            ("Applications open until 15th September 2026 for all students.", datetime(2026, 9, 15, tzinfo=timezone.utc)),
            ("Registration deadline: September 20, 2026 at midnight.", datetime(2026, 9, 20, tzinfo=timezone.utc)),
            ("Last date to apply: 2026-10-31.", datetime(2026, 10, 31, tzinfo=timezone.utc)),
            ("Contest ends on 05/11/2026.", datetime(2026, 11, 5, tzinfo=timezone.utc)),
        ]
        for text, expected_dt in texts:
            dl = DateExtractor.extract_deadline(text)
            self.assertIsNotNone(dl, f"Failed to extract deadline from: {text}")
            self.assertEqual(dl.parsed_date.year, expected_dt.year)
            self.assertEqual(dl.parsed_date.month, expected_dt.month)
            self.assertEqual(dl.parsed_date.day, expected_dt.day)

    def test_deadline_evaluator(self):
        """Test evaluation of deadline announcements, extensions, and shortenings."""
        d1 = datetime(2026, 9, 10, tzinfo=timezone.utc)
        d2 = datetime(2026, 9, 20, tzinfo=timezone.utc)
        d3 = datetime(2026, 9, 5, tzinfo=timezone.utc)

        ev_type, reason = DeadlineEvaluator.evaluate(None, d1)
        self.assertEqual(ev_type, EventType.DEADLINE_ANNOUNCED)
        self.assertIn("announced", reason.lower())

        ev_type, reason = DeadlineEvaluator.evaluate(d1, d2)
        self.assertEqual(ev_type, EventType.DEADLINE_EXTENDED)
        self.assertIn("extended", reason.lower())

        ev_type, reason = DeadlineEvaluator.evaluate(d2, d3)
        self.assertEqual(ev_type, EventType.DEADLINE_SHORTENED)
        self.assertIn("shortened", reason.lower())

        ev_type, reason = DeadlineEvaluator.evaluate(d1, d1)
        self.assertIsNone(ev_type)

    # =========================================================================
    # PART 3: Meaningful Change Detection Tests
    # =========================================================================
    def test_meaningful_change_detector_ignores_noise(self):
        """Test that timestamps, visitor counters, and whitespace changes are ignored."""
        old_text = (
            "Smart India Hackathon 2026\n"
            "Problem statements released for students.\n"
            "Last updated at 10:01 AM on 12/09/2026\n"
            "Page views: 1,420\n"
            "Accept cookies to continue."
        )
        new_text = (
            "Smart India Hackathon 2026\n"
            "Problem statements released for students.  \n"
            "Last updated at 10:05 AM on 12/09/2026\n"
            "Page views: 1,489\n"
            "We use cookies."
        )
        evaluation = MeaningfulChangeDetector.evaluate_difference(old_text, new_text, 10, 10)
        self.assertFalse(evaluation.is_meaningful)
        self.assertEqual(evaluation.change_type, ChangeType.NO_CHANGE)

    def test_meaningful_change_detector_detects_status_and_items(self):
        """Test that registration status shifts and item additions are detected."""
        old_text = "TCS CodeVita Season 13 will be announced soon."
        new_text = "TCS CodeVita Season 13 registrations open now! Apply before deadline."

        eval_status = MeaningfulChangeDetector.evaluate_difference(old_text, new_text, 1, 1)
        self.assertTrue(eval_status.is_meaningful)
        self.assertEqual(eval_status.change_type, ChangeType.STATUS_CHANGED)

        eval_items = MeaningfulChangeDetector.evaluate_difference(old_text, old_text, 5, 8)
        self.assertTrue(eval_items.is_meaningful)
        self.assertEqual(eval_items.change_type, ChangeType.NEW_ITEM)

    # =========================================================================
    # PART 4: Connector Contract & Mock Tests
    # =========================================================================
    def test_new_connectors_initialization_contracts(self):
        """Validate initialization contracts on all new connectors."""
        connectors = [
            CodeChefConnector(),
            HackerRankConnector(),
            LeetCodeConnector(),
            GSoCConnector(),
            MyGovConnector(),
            MLHConnector(),
        ]
        for conn in connectors:
            self.assert_connector_initialization(conn)


class TestSourceIntelligenceDB(unittest.IsolatedAsyncioTestCase, ConnectorContractTestMixin):
    """Database and integration tests for Snapshots, OrganizationAlias, Health, and REST APIs."""

    async def asyncSetUp(self):
        """Set up isolated in-memory SQLite database."""
        self.engine = create_async_engine(
            "sqlite+aiosqlite:///:memory:",
            echo=False,
            future=True,
        )
        self.session_factory = async_sessionmaker(
            bind=self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        self.db = self.session_factory()

    async def asyncTearDown(self):
        """Clean up database connections."""
        await self.db.close()
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await self.engine.dispose()

    # =========================================================================
    # PART 5: Connector Fetch & Normalization Tests
    # =========================================================================
    async def test_codechef_connector_normalization(self):
        """Test CodeChef fetch and normalization using mock API response."""
        conn = CodeChefConnector()
        mock_payload = {
            "status": "success",
            "present_contests": [
                {
                    "contest_code": "START150",
                    "contest_name": "Starters 150 (Rated)",
                    "contest_start_date_iso": "2026-09-16T14:30:00Z",
                    "contest_end_date_iso": "2026-09-16T16:30:00Z",
                }
            ],
            "future_contests": [
                {
                    "contest_code": "START151",
                    "contest_name": "Starters 151 (Rated)",
                    "contest_start_date_iso": "2026-09-23T14:30:00Z",
                    "contest_end_date_iso": "2026-09-23T16:30:00Z",
                }
            ],
        }

        with patch("services.ingestion.http_client.ResilientHTTPClient.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = mock_payload
            mock_get.return_value = mock_resp

            items = await conn.fetch_raw_items()
            self.assertEqual(len(items), 2)
            self.assert_raw_items_contract(items, "CodeChef")
            self.assertEqual(items[0].source_identifier, "codechef-START150")
            self.assertIn("START150", items[0].url)

    async def test_hackerrank_connector_normalization(self):
        """Test HackerRank fetch and normalization with mock response."""
        conn = HackerRankConnector()
        mock_payload = {
            "models": [
                {
                    "slug": "orchestrate-sep26",
                    "name": "Orchestrate September 2026",
                    "epoch_starttime": 1789216200,
                    "epoch_endtime": 1789223400,
                    "description": "Annual orchestration coding challenge.",
                }
            ]
        }
        with patch("services.ingestion.http_client.ResilientHTTPClient.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = mock_payload
            mock_get.return_value = mock_resp

            items = await conn.fetch_raw_items()
            self.assertEqual(len(items), 1)
            self.assert_raw_items_contract(items, "HackerRank")
            self.assertEqual(items[0].source_identifier, "hackerrank-orchestrate-sep26")

    async def test_leetcode_connector_normalization(self):
        """Test LeetCode fetch and normalization with mock GraphQL response."""
        conn = LeetCodeConnector(lookback_days=30)
        mock_payload = {
            "data": {
                "allContests": [
                    {
                        "title": "Weekly Contest 520",
                        "titleSlug": "weekly-contest-520",
                        "startTime": int(datetime.now(timezone.utc).timestamp()) + 86400,
                        "duration": 5400,
                    }
                ]
            }
        }
        with patch("services.ingestion.http_client.ResilientHTTPClient.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = mock_payload
            mock_post.return_value = mock_resp

            items = await conn.fetch_raw_items()
            self.assertEqual(len(items), 1)
            self.assert_raw_items_contract(items, "LeetCode")
            self.assertEqual(items[0].source_identifier, "leetcode-weekly-contest-520")

    # =========================================================================
    # PART 6: Source Snapshot Persistence Tests
    # =========================================================================
    async def test_snapshot_manager_lifecycle(self):
        """Test recording snapshots in database and computing diffs."""
        source = Source(
            name="Test Portal",
            slug="test-portal",
            category=OpportunityCategory.HACKATHON.value,
            source_type=SourceType.OFFICIAL_WEBSITE.value,
            base_url="https://test.internal",
        )
        self.db.add(source)
        await self.db.commit()

        mgr = SnapshotManager(self.db)

        # Baseline snapshot
        snap1, eval1 = await mgr.record_snapshot(
            source_id=source.id,
            raw_content="Season 1: Registrations will open in October.",
            items_count=1,
        )
        await self.db.commit()
        self.assertEqual(snap1.change_type, ChangeType.NEW_ITEM.value)
        self.assertTrue(eval1.is_meaningful)

        # Identical content snapshot
        snap2, eval2 = await mgr.record_snapshot(
            source_id=source.id,
            raw_content="Season 1: Registrations will open in October.",
            items_count=1,
        )
        await self.db.commit()
        self.assertEqual(snap2.change_type, ChangeType.NO_CHANGE.value)
        self.assertFalse(eval2.is_meaningful)

        # Changed content snapshot
        snap3, eval3 = await mgr.record_snapshot(
            source_id=source.id,
            raw_content="Season 1: Registrations open now! Last date 15th November 2026.",
            items_count=2,
        )
        await self.db.commit()
        self.assertTrue(eval3.is_meaningful)

    # =========================================================================
    # PART 7: Organization Alias Resolution Tests
    # =========================================================================
    async def test_organization_alias_resolution(self):
        """Test resolving Organization from alternative aliases."""
        org = Organization(
            name="Tata Consultancy Services",
            slug="tata-consultancy-services",
            is_verified=True,
        )
        self.db.add(org)
        await self.db.flush()

        alias = OrganizationAlias(
            organization_id=org.id,
            alias="TCS",
            normalized_alias="tcs",
        )
        self.db.add(alias)
        await self.db.commit()

        lifecycle_engine = LifecycleEngine(self.db)

        resolved = await lifecycle_engine.get_or_create_organization("TCS")
        self.assertIsNotNone(resolved)
        self.assertEqual(resolved.id, org.id)
        self.assertEqual(resolved.name, "Tata Consultancy Services")

    # =========================================================================
    # PART 8: Connector Health Tracking Tests
    # =========================================================================
    async def test_connector_health_state_transitions(self):
        """Test healthy -> degraded -> failing status transitions upon successive errors."""
        pipeline = IngestionPipeline(self.db)
        mock_conn = MagicMock()
        mock_conn.name = "Test Fragile Source"
        mock_conn.category = OpportunityCategory.COMPETITIVE_PROGRAMMING
        mock_conn.source_type = SourceType.API
        mock_conn.trust_level = TrustLevel.HIGH
        mock_conn.base_url = "https://fragile.internal"
        mock_conn.is_active = True
        mock_conn.fetch_raw_items = AsyncMock(side_effect=RuntimeError("Connection refused"))

        for _ in range(2):
            with self.assertRaises(RuntimeError):
                await pipeline.process_connector(mock_conn)

        src = (await self.db.execute(select(Source).where(Source.slug == "test-fragile-source"))).scalars().first()
        self.assertEqual(src.consecutive_failures, 2)
        self.assertEqual(src.status, SourceHealthStatus.HEALTHY.value)

        # Failure 3 -> DEGRADED
        with self.assertRaises(RuntimeError):
            await pipeline.process_connector(mock_conn)
        await self.db.refresh(src)
        self.assertEqual(src.consecutive_failures, 3)
        self.assertEqual(src.status, SourceHealthStatus.DEGRADED.value)

        # Failures 4 and 5 -> FAILING
        for _ in range(2):
            with self.assertRaises(RuntimeError):
                await pipeline.process_connector(mock_conn)
        await self.db.refresh(src)
        self.assertEqual(src.consecutive_failures, 5)
        self.assertEqual(src.status, SourceHealthStatus.FAILING.value)

    # =========================================================================
    # PART 9: Sources & Dashboard REST API Tests
    # =========================================================================
    async def test_sources_and_dashboard_api_endpoints(self):
        """Test /api/v1/sources and /api/v1/dashboard REST endpoints."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res_sources = await client.get("/api/v1/sources")
            self.assertEqual(res_sources.status_code, 200)
            data = res_sources.json()
            self.assertIn("items", data)

            res_dash = await client.get("/api/v1/dashboard/sources")
            self.assertEqual(res_dash.status_code, 200)
            dash_data = res_dash.json()
            self.assertIn("total_sources", dash_data)
            self.assertIn("healthy_sources", dash_data)

            res_act = await client.get("/api/v1/dashboard/activity")
            self.assertEqual(res_act.status_code, 200)
            self.assertIsInstance(res_act.json(), list)


if __name__ == "__main__":
    unittest.main()
