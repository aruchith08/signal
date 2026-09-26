"""
Tests for Phase 6B: Unstop Productionization & End-to-End Live Polling Pipeline

Validates:
- TEST 1: Idempotent Unstop Source registration (running twice yields same source.id)
- TEST 2: Scheduler coordinator discovers Unstop when due
- TEST 3: Scheduler poll_source("unstop", db) resolves UnstopConnector and executes successfully
- TEST 4: Successful poll creates ScheduledJob record with status="success"
- TEST 5: Repeated identical ingestion does not create duplicate Opportunity
- TEST 6: Changed Unstop data (e.g. deadline changed) creates ChangeSet with field_name="deadline_date", importance="critical"
- TEST 7: Connector failure marks ScheduledJob as failure and increments Source.consecutive_failures without raising unhandled errors
- TEST 8: When Source.scheduler_enabled = False, scheduler coordinator does not include Unstop in due_slugs
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import unittest
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI
from httpx import Request, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from apps.api.models import ChangeSet, Opportunity, OpportunityEvent, ScheduledJob, Source
from apps.api.models.base import Base
from apps.api.models.discovery import RawDiscovery
from connectors.unstop import UnstopConnector
from services.scheduler.scheduler import coordinator_job, get_connector, poll_source
from services.sources.registry import ensure_unstop_source, source_registry
from shared.constants import (
    ChangeType,
    DiscoveryStatus,
    OpportunityCategory,
    OpportunityStatus,
    PollingPolicy,
    PriorityLevel,
    ScheduledJobStatus,
    SourceHealthStatus,
    SourceType,
    TrustLevel,
)


SAMPLE_UNSTOP_PAYLOAD = {
    "data": {
        "current_page": 1,
        "total": 1,
        "data": [
            {
                "id": 880011,
                "title": "National AI Breakthrough Hackathon 2026",
                "seo_url": "https://unstop.com/hackathons/national-ai-breakthrough-hackathon-2026-880011",
                "type": "hackathons",
                "subtype": "open_innovation",
                "details": "Premier national AI hackathon for students and builders across universities.",
                "region": "online",
                "start_date": "2026-10-01T09:00:00+05:30",
                "end_date": "2026-10-15T23:59:00+05:30",
                "organisation": {
                    "id": 5510,
                    "name": "National Innovation Council",
                },
                "regnRequirements": {
                    "start_regn_dt": "2026-09-15T00:00:00+05:30",
                    "end_regn_dt": "2026-10-15T23:59:00+05:30",
                    "eligibility": "B.Tech / MCA / Dual degree students",
                    "min_team_size": 2,
                    "max_team_size": 4,
                },
                "required_skills": [
                    {"skill_name": "Python"},
                    {"skill_name": "PyTorch"},
                ],
                "prizes": [
                    {"rank": "1st Prize", "cash": 150000},
                ],
            }
        ],
    }
}


class TestUnstopProductionPipeline(unittest.IsolatedAsyncioTestCase):
    """Full lifecycle & scheduler verification tests for Unstop source productionization."""

    async def asyncSetUp(self):
        self.engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        self.session_factory = async_sessionmaker(
            bind=self.engine, class_=AsyncSession, expire_on_commit=False
        )
        self.app = FastAPI()

    async def asyncTearDown(self):
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await self.engine.dispose()

    # =========================================================================
    # TEST 1: Idempotent Unstop Source Registration
    # =========================================================================
    async def test_1_idempotent_unstop_source_registration(self):
        """Registering Unstop source multiple times produces the exact same DB entity without duplicates."""
        async with self.session_factory() as session:
            src1 = await ensure_unstop_source(session)
            await session.commit()
            src1_id = src1.id

            # Verify production default attributes
            self.assertEqual(src1.slug, "unstop")
            self.assertEqual(src1.name, "Unstop")
            self.assertEqual(src1.source_type, SourceType.API.value)
            self.assertEqual(src1.category, OpportunityCategory.TECH_COMPETITION.value)
            self.assertEqual(src1.base_url, "https://unstop.com")
            self.assertTrue(src1.is_active)
            self.assertTrue(src1.scheduler_enabled)
            self.assertEqual(src1.monitor_frequency_minutes, 60)
            self.assertEqual(src1.polling_policy, PollingPolicy.HIGH_PRIORITY.value)
            self.assertEqual(src1.trust_level, TrustLevel.HIGH.value)
            self.assertEqual(src1.status, SourceHealthStatus.HEALTHY.value)

        # Second call in a new session
        async with self.session_factory() as session:
            src2 = await ensure_unstop_source(session)
            await session.commit()
            self.assertEqual(src2.id, src1_id)

            # Ensure only 1 row exists in DB
            count_stmt = select(func.count(Source.id)).where(Source.slug == "unstop")
            total_unstop = (await session.execute(count_stmt)).scalar()
            self.assertEqual(total_unstop, 1)

    # =========================================================================
    # TEST 2: Scheduler Coordinator Discovers Unstop When Due
    # =========================================================================
    async def test_2_scheduler_coordinator_discovers_unstop_when_due(self):
        """Coordinator must discover Unstop when is_active=True, scheduler_enabled=True, and interval has elapsed."""
        now = datetime.now(timezone.utc)
        async with self.session_factory() as session:
            unstop_src = await ensure_unstop_source(session)
            # HIGH_PRIORITY interval is 30 minutes; setting last_polled_at to 45m ago makes it due
            unstop_src.last_polled_at = now - timedelta(minutes=45)
            await session.commit()

        polled_slugs = []

        async def fake_poll_source(slug: str, db: AsyncSession):
            polled_slugs.append(slug)

        with patch("services.scheduler.scheduler.AsyncSessionLocal", self.session_factory):
            with patch("services.scheduler.scheduler.poll_source", fake_poll_source):
                await coordinator_job(self.app)

        self.assertIn("unstop", polled_slugs)

    # =========================================================================
    # TEST 3: Scheduler poll_source Resolves and Executes UnstopConnector
    # =========================================================================
    @patch("services.ingestion.http_client.ResilientHTTPClient.get")
    async def test_3_scheduler_poll_source_resolves_and_executes(self, mock_get):
        """poll_source('unstop') resolves UnstopConnector via CONNECTOR_REGISTRY and successfully ingests."""
        mock_get.return_value = Response(
            status_code=200,
            json=SAMPLE_UNSTOP_PAYLOAD,
            request=Request("GET", "https://unstop.com/api/public/opportunity/search-result"),
        )

        connector_cls = get_connector("unstop")
        self.assertIs(connector_cls, UnstopConnector)

        async with self.session_factory() as session:
            await ensure_unstop_source(session)
            await session.commit()

        async with self.session_factory() as session:
            await poll_source("unstop", session)

        async with self.session_factory() as session:
            opp_stmt = select(Opportunity).where(Opportunity.title == "National AI Breakthrough Hackathon 2026")
            opp = (await session.execute(opp_stmt)).scalar_one_or_none()
            self.assertIsNotNone(opp)
            self.assertEqual(opp.category, OpportunityCategory.HACKATHON.value)
            self.assertEqual(opp.status, OpportunityStatus.ACTIVE.value)

    # =========================================================================
    # TEST 4: Successful Poll Creates ScheduledJob Record
    # =========================================================================
    @patch("services.ingestion.http_client.ResilientHTTPClient.get")
    async def test_4_successful_poll_creates_scheduled_job(self, mock_get):
        """A successful poll creates a ScheduledJob audit record with status=success and updates Source metrics."""
        mock_get.return_value = Response(
            status_code=200,
            json=SAMPLE_UNSTOP_PAYLOAD,
            request=Request("GET", "https://unstop.com/api/public/opportunity/search-result"),
        )

        async with self.session_factory() as session:
            src = await ensure_unstop_source(session)
            src.consecutive_failures = 3
            await session.commit()
            src_id = src.id

        async with self.session_factory() as session:
            await poll_source("unstop", session)

        async with self.session_factory() as session:
            job_stmt = select(ScheduledJob).where(ScheduledJob.source_id == src_id)
            job = (await session.execute(job_stmt)).scalars().first()
            self.assertIsNotNone(job)
            self.assertEqual(job.status, ScheduledJobStatus.SUCCESS.value)
            self.assertEqual(job.items_discovered, 1)
            self.assertEqual(job.items_processed, 1)
            self.assertIsNotNone(job.duration_ms)
            self.assertIsNotNone(job.started_at)
            self.assertIsNotNone(job.finished_at)

            # Check source counters reset
            src_stmt = select(Source).where(Source.id == src_id)
            updated_src = (await session.execute(src_stmt)).scalar_one()
            self.assertEqual(updated_src.consecutive_failures, 0)
            self.assertEqual(updated_src.failure_count, 0)
            self.assertIsNotNone(updated_src.last_polled_at)
            self.assertIsNotNone(updated_src.last_successful_check)

    # =========================================================================
    # TEST 5: Repeated Identical Ingestion Does Not Create Duplicate Opportunity
    # =========================================================================
    @patch("services.ingestion.http_client.ResilientHTTPClient.get")
    async def test_5_repeated_identical_ingestion_no_duplicate(self, mock_get):
        """Repeated polls with identical payload do not generate duplicate Opportunities or ChangeSets."""
        mock_get.return_value = Response(
            status_code=200,
            json=SAMPLE_UNSTOP_PAYLOAD,
            request=Request("GET", "https://unstop.com/api/public/opportunity/search-result"),
        )

        # 1st Poll
        async with self.session_factory() as session:
            await ensure_unstop_source(session)
            await session.commit()

        async with self.session_factory() as session:
            await poll_source("unstop", session)

        async with self.session_factory() as session:
            opp_count = (await session.execute(select(func.count(Opportunity.id)))).scalar()
            self.assertEqual(opp_count, 1)
            disc_count = (await session.execute(select(func.count(RawDiscovery.id)))).scalar()
            self.assertEqual(disc_count, 1)
            cs_count = (await session.execute(select(func.count(ChangeSet.id)))).scalar()
            self.assertEqual(cs_count, 0)

        # 2nd Poll (Identical payload)
        async with self.session_factory() as session:
            await poll_source("unstop", session)

        async with self.session_factory() as session:
            opp_count_after = (await session.execute(select(func.count(Opportunity.id)))).scalar()
            self.assertEqual(opp_count_after, 1, "Must not create duplicate Opportunity on repeated poll")
            cs_count_after = (await session.execute(select(func.count(ChangeSet.id)))).scalar()
            self.assertEqual(cs_count_after, 0, "Must not create ChangeSet on identical data")

    # =========================================================================
    # TEST 6: Changed Unstop Data Creates ChangeSet
    # =========================================================================
    @patch("services.ingestion.http_client.ResilientHTTPClient.get")
    async def test_6_changed_unstop_data_creates_changeset(self, mock_get):
        """Modifying an existing opportunity's deadline generates a critical ChangeSet with previous and new values."""
        # Poll 1: Original deadline is 2026-10-15
        mock_get.return_value = Response(
            status_code=200,
            json=SAMPLE_UNSTOP_PAYLOAD,
            request=Request("GET", "https://unstop.com/api/public/opportunity/search-result"),
        )

        async with self.session_factory() as session:
            await ensure_unstop_source(session)
            await session.commit()

        async with self.session_factory() as session:
            await poll_source("unstop", session)

        async with self.session_factory() as session:
            opp = (await session.execute(select(Opportunity))).scalars().first()
            opp_id = opp.id

        # Poll 2: Modified deadline extended to 2026-11-05
        updated_payload = {
            "data": {
                "current_page": 1,
                "total": 1,
                "data": [
                    {
                        "id": 880011,
                        "title": "National AI Breakthrough Hackathon 2026",
                        "seo_url": "https://unstop.com/hackathons/national-ai-breakthrough-hackathon-2026-880011",
                        "type": "hackathons",
                        "subtype": "open_innovation",
                        "details": "Premier national AI hackathon for students and builders across universities. Registration extended!",
                        "region": "online",
                        "start_date": "2026-10-01T09:00:00+05:30",
                        "end_date": "2026-11-05T23:59:00+05:30",
                        "organisation": {
                            "id": 5510,
                            "name": "National Innovation Council",
                        },
                        "regnRequirements": {
                            "start_regn_dt": "2026-09-15T00:00:00+05:30",
                            "end_regn_dt": "2026-11-05T23:59:00+05:30",
                            "eligibility": "B.Tech / MCA / Dual degree students",
                            "min_team_size": 2,
                            "max_team_size": 4,
                        },
                        "required_skills": [
                            {"skill_name": "Python"},
                            {"skill_name": "PyTorch"},
                        ],
                        "prizes": [
                            {"rank": "1st Prize", "cash": 150000},
                        ],
                    }
                ],
            }
        }
        mock_get.return_value = Response(
            status_code=200,
            json=updated_payload,
            request=Request("GET", "https://unstop.com/api/public/opportunity/search-result"),
        )

        async with self.session_factory() as session:
            await poll_source("unstop", session)

        async with self.session_factory() as session:
            cs_stmt = select(ChangeSet).where(ChangeSet.opportunity_id == opp_id)
            changesets = (await session.execute(cs_stmt)).scalars().all()
            self.assertGreaterEqual(len(changesets), 1, "ChangeSet must be created on deadline update")

            deadline_cs = [c for c in changesets if c.field_name == "deadline_date"]
            self.assertEqual(len(deadline_cs), 1)
            cs = deadline_cs[0]
            self.assertEqual(cs.change_type, ChangeType.DEADLINE_CHANGED.value)
            self.assertEqual(cs.importance, PriorityLevel.CRITICAL.value)
            self.assertIn("2026-10-15", cs.previous_value)
            self.assertIn("2026-11-05", cs.new_value)

    # =========================================================================
    # TEST 7: Connector Failure Marks ScheduledJob and Increments Counters
    # =========================================================================
    async def test_7_connector_failure_updates_job_and_source_counters(self):
        """Connector failure logs failure in ScheduledJob and increments Source failure count without raising."""
        async with self.session_factory() as session:
            src = await ensure_unstop_source(session)
            await session.commit()
            src_id = src.id

        # Simulate exception during ingestion pipeline processing
        with patch("services.scheduler.scheduler.IngestionPipeline") as mock_pipe_cls:
            mock_pipe = AsyncMock()
            mock_pipe.process_connector.side_effect = RuntimeError("Unstop API service timed out after 3 retries")
            mock_pipe_cls.return_value = mock_pipe

            async with self.session_factory() as session:
                # Must not raise to caller
                await poll_source("unstop", session)

        async with self.session_factory() as session:
            job_stmt = select(ScheduledJob).where(ScheduledJob.source_id == src_id)
            job = (await session.execute(job_stmt)).scalars().first()
            self.assertIsNotNone(job)
            self.assertEqual(job.status, ScheduledJobStatus.FAILURE.value)
            self.assertIn("timed out", job.error_message)

            src_stmt = select(Source).where(Source.id == src_id)
            updated_src = (await session.execute(src_stmt)).scalar_one()
            self.assertEqual(updated_src.consecutive_failures, 1)
            self.assertEqual(updated_src.failure_count, 1)
            self.assertIn("timed out", updated_src.last_error)

    # =========================================================================
    # TEST 8: Scheduler Disabled Source Not Polled By Coordinator
    # =========================================================================
    async def test_8_scheduler_disabled_source_not_polled(self):
        """When Source.scheduler_enabled=False, coordinator ignores the source even if last_polled_at is stale."""
        now = datetime.now(timezone.utc)
        async with self.session_factory() as session:
            unstop_src = await ensure_unstop_source(session)
            unstop_src.scheduler_enabled = False
            unstop_src.last_polled_at = now - timedelta(days=5)
            await session.commit()

        polled_slugs = []

        async def fake_poll_source(slug: str, db: AsyncSession):
            polled_slugs.append(slug)

        with patch("services.scheduler.scheduler.AsyncSessionLocal", self.session_factory):
            with patch("services.scheduler.scheduler.poll_source", fake_poll_source):
                await coordinator_job(self.app)

        self.assertNotIn("unstop", polled_slugs)


if __name__ == "__main__":
    unittest.main()
