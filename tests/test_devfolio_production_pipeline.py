"""
Tests for Phase 6C: Devfolio Productionization & End-to-End Live Polling Pipeline

Validates:
- TEST 1: Connector registration works and adheres to BaseConnector contract
- TEST 2: Source registration is idempotent (running twice yields same source.id)
- TEST 3: Scheduler coordinator discovers Devfolio when due
- TEST 4: Scheduler poll_source("devfolio", db) resolves DevfolioConnector and executes successfully
- TEST 5: Successful poll creates ScheduledJob record with status="success"
- TEST 6: Repeated identical ingestion creates no duplicate Opportunity or ChangeSet
- TEST 7: Changed data produces structured ChangeSet on modified deadline
- TEST 8: Connector failure marks ScheduledJob as failure and increments Source.consecutive_failures without crashing
- TEST 9: When Source.scheduler_enabled = False, scheduler coordinator omits Devfolio from due_slugs
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
from connectors.devfolio import DevfolioConnector
from services.scheduler.scheduler import coordinator_job, get_connector, poll_source
from services.sources.registry import ensure_devfolio_source, source_registry
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
from tests.helpers.connector_contract import ConnectorContractTestMixin


SAMPLE_DEVFOLIO_PAYLOAD = {
    "hits": {
        "total": {"value": 1},
        "hits": [
            {
                "_source": {
                    "uuid": "devfolio-uuid-778899",
                    "name": "HackSpire'26 National Hackathon",
                    "slug": "hackspire26",
                    "tagline": "Inspiring next-gen engineers to build decentralized applications.",
                    "desc": "Official student hackathon organized by ACM Student Chapter. Win prizes and mentorship.",
                    "hosted_by": "ACM Student Chapter",
                    "starts_at": "2026-10-02T08:30:00+00:00",
                    "ends_at": "2026-10-03T10:30:00+00:00",
                    "registrations_start": "2026-09-01T00:00:00+00:00",
                    "registrations_end": "2026-09-28T23:59:00+00:00",
                    "is_online": True,
                    "apply_mode": "online",
                    "city": "Bengaluru",
                    "state": "Karnataka",
                    "country": "India",
                    "location": "Online / Virtual",
                    "team_min": 2,
                    "team_size": 4,
                    "themes": [{"name": "AI"}, {"name": "Blockchain"}],
                    "hashtags": ["web3", "machine-learning"],
                    "prizes": [
                        {"name": "Grand Prize", "desc": "100,000 INR cash prize"},
                        {"name": "Runner Up", "desc": "50,000 INR cash prize"},
                    ],
                }
            }
        ],
    }
}


class TestDevfolioProductionPipeline(unittest.IsolatedAsyncioTestCase, ConnectorContractTestMixin):
    """Full lifecycle & scheduler verification tests for Devfolio source productionization."""

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
    # TEST 1: Connector Registration & Contract Compliance
    # =========================================================================
    def test_1_connector_registration_and_contract(self):
        """DevfolioConnector is registered in CONNECTOR_REGISTRY and adheres to BaseConnector contract."""
        connector_cls = get_connector("devfolio")
        self.assertIs(connector_cls, DevfolioConnector)

        connector = DevfolioConnector()
        self.assert_connector_initialization(connector)
        self.assertEqual(connector.name, "Devfolio")
        self.assertEqual(connector.source_type, SourceType.API)
        self.assertEqual(connector.category, OpportunityCategory.HACKATHON)
        self.assertEqual(connector.trust_level, TrustLevel.HIGH)
        self.assertEqual(connector.base_url, "https://devfolio.co")

        # Verify catalog registration
        source_def = source_registry.get("devfolio")
        self.assertIsNotNone(source_def)
        self.assertEqual(source_def.connector_class, DevfolioConnector)
        self.assertTrue(source_def.enabled)
        self.assertEqual(source_def.polling_policy, PollingPolicy.HIGH_PRIORITY)

    # =========================================================================
    # TEST 2: Idempotent Source Registration
    # =========================================================================
    async def test_2_idempotent_devfolio_source_registration(self):
        """Registering Devfolio source multiple times produces the exact same DB entity without duplicates."""
        async with self.session_factory() as session:
            src1 = await ensure_devfolio_source(session)
            await session.commit()
            src1_id = src1.id

            # Verify production default attributes
            self.assertEqual(src1.slug, "devfolio")
            self.assertEqual(src1.name, "Devfolio")
            self.assertEqual(src1.source_type, SourceType.API.value)
            self.assertEqual(src1.category, OpportunityCategory.HACKATHON.value)
            self.assertEqual(src1.base_url, "https://devfolio.co")
            self.assertTrue(src1.is_active)
            self.assertTrue(src1.scheduler_enabled)
            self.assertEqual(src1.monitor_frequency_minutes, 60)
            self.assertEqual(src1.polling_policy, PollingPolicy.HIGH_PRIORITY.value)
            self.assertEqual(src1.trust_level, TrustLevel.HIGH.value)
            self.assertEqual(src1.status, SourceHealthStatus.HEALTHY.value)

        # Second call in a new session
        async with self.session_factory() as session:
            src2 = await ensure_devfolio_source(session)
            await session.commit()
            self.assertEqual(src2.id, src1_id)

            # Ensure only 1 row exists in DB
            count_stmt = select(func.count(Source.id)).where(Source.slug == "devfolio")
            total_devfolio = (await session.execute(count_stmt)).scalar()
            self.assertEqual(total_devfolio, 1)

    # =========================================================================
    # TEST 3: Scheduler Coordinator Discovers Devfolio When Due
    # =========================================================================
    async def test_3_scheduler_coordinator_discovers_devfolio_when_due(self):
        """Coordinator must discover Devfolio when is_active=True, scheduler_enabled=True, and interval has elapsed."""
        now = datetime.now(timezone.utc)
        async with self.session_factory() as session:
            devfolio_src = await ensure_devfolio_source(session)
            # HIGH_PRIORITY interval is 30 minutes; setting last_polled_at to 45m ago makes it due
            devfolio_src.last_polled_at = now - timedelta(minutes=45)
            await session.commit()

        polled_slugs = []

        async def fake_poll_source(slug: str, db: AsyncSession):
            polled_slugs.append(slug)

        with patch("services.scheduler.scheduler.AsyncSessionLocal", self.session_factory):
            with patch("services.scheduler.scheduler.poll_source", fake_poll_source):
                await coordinator_job(self.app)

        self.assertIn("devfolio", polled_slugs)

    # =========================================================================
    # TEST 4: Scheduler poll_source Resolves and Executes DevfolioConnector
    # =========================================================================
    @patch("services.ingestion.http_client.ResilientHTTPClient.post")
    async def test_4_scheduler_poll_source_resolves_and_executes(self, mock_post):
        """poll_source('devfolio') resolves DevfolioConnector via CONNECTOR_REGISTRY and successfully ingests."""
        mock_post.return_value = Response(
            status_code=200,
            json=SAMPLE_DEVFOLIO_PAYLOAD,
            request=Request("POST", "https://api.devfolio.co/api/search/hackathons"),
        )

        async with self.session_factory() as session:
            await ensure_devfolio_source(session)
            await session.commit()

        async with self.session_factory() as session:
            await poll_source("devfolio", session)

        async with self.session_factory() as session:
            opp_stmt = select(Opportunity).where(Opportunity.title == "HackSpire'26 National Hackathon")
            opp = (await session.execute(opp_stmt)).scalar_one_or_none()
            self.assertIsNotNone(opp)
            self.assertEqual(opp.category, OpportunityCategory.HACKATHON.value)
            self.assertEqual(opp.status, OpportunityStatus.ACTIVE.value)

    # =========================================================================
    # TEST 5: Successful Poll Creates ScheduledJob Record
    # =========================================================================
    @patch("services.ingestion.http_client.ResilientHTTPClient.post")
    async def test_5_successful_poll_creates_scheduled_job(self, mock_post):
        """A successful poll creates a ScheduledJob audit record with status=success and updates Source metrics."""
        mock_post.return_value = Response(
            status_code=200,
            json=SAMPLE_DEVFOLIO_PAYLOAD,
            request=Request("POST", "https://api.devfolio.co/api/search/hackathons"),
        )

        async with self.session_factory() as session:
            src = await ensure_devfolio_source(session)
            src.consecutive_failures = 2
            await session.commit()
            src_id = src.id

        async with self.session_factory() as session:
            await poll_source("devfolio", session)

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
    # TEST 6: Repeated Identical Ingestion Does Not Create Duplicate Opportunity
    # =========================================================================
    @patch("services.ingestion.http_client.ResilientHTTPClient.post")
    async def test_6_repeated_identical_ingestion_no_duplicate(self, mock_post):
        """Repeated polls with identical payload do not generate duplicate Opportunities or ChangeSets."""
        mock_post.return_value = Response(
            status_code=200,
            json=SAMPLE_DEVFOLIO_PAYLOAD,
            request=Request("POST", "https://api.devfolio.co/api/search/hackathons"),
        )

        # 1st Poll
        async with self.session_factory() as session:
            await ensure_devfolio_source(session)
            await session.commit()

        async with self.session_factory() as session:
            await poll_source("devfolio", session)

        async with self.session_factory() as session:
            opp_count = (await session.execute(select(func.count(Opportunity.id)))).scalar()
            self.assertEqual(opp_count, 1)
            disc_count = (await session.execute(select(func.count(RawDiscovery.id)))).scalar()
            self.assertEqual(disc_count, 1)
            cs_count = (await session.execute(select(func.count(ChangeSet.id)))).scalar()
            self.assertEqual(cs_count, 0)

        # 2nd Poll (Identical payload)
        async with self.session_factory() as session:
            await poll_source("devfolio", session)

        async with self.session_factory() as session:
            opp_count_after = (await session.execute(select(func.count(Opportunity.id)))).scalar()
            self.assertEqual(opp_count_after, 1, "Must not create duplicate Opportunity on repeated poll")
            cs_count_after = (await session.execute(select(func.count(ChangeSet.id)))).scalar()
            self.assertEqual(cs_count_after, 0, "Must not create ChangeSet on identical data")

    # =========================================================================
    # TEST 7: Changed Devfolio Data Creates ChangeSet
    # =========================================================================
    @patch("services.ingestion.http_client.ResilientHTTPClient.post")
    async def test_7_changed_devfolio_data_creates_changeset(self, mock_post):
        """Modifying an existing opportunity's deadline generates a critical ChangeSet with previous and new values."""
        # Poll 1: Original deadline is 2026-09-28
        mock_post.return_value = Response(
            status_code=200,
            json=SAMPLE_DEVFOLIO_PAYLOAD,
            request=Request("POST", "https://api.devfolio.co/api/search/hackathons"),
        )

        async with self.session_factory() as session:
            await ensure_devfolio_source(session)
            await session.commit()

        async with self.session_factory() as session:
            await poll_source("devfolio", session)

        async with self.session_factory() as session:
            opp = (await session.execute(select(Opportunity))).scalars().first()
            opp_id = opp.id

        # Poll 2: Modified registration deadline extended to 2026-10-10
        updated_payload = {
            "hits": {
                "total": {"value": 1},
                "hits": [
                    {
                        "_source": {
                            "uuid": "devfolio-uuid-778899",
                            "name": "HackSpire'26 National Hackathon",
                            "slug": "hackspire26",
                            "tagline": "Inspiring next-gen engineers to build decentralized applications.",
                            "desc": "Official student hackathon organized by ACM Student Chapter. Registration extended!",
                            "hosted_by": "ACM Student Chapter",
                            "starts_at": "2026-10-02T08:30:00+00:00",
                            "ends_at": "2026-10-03T10:30:00+00:00",
                            "registrations_start": "2026-09-01T00:00:00+00:00",
                            "registrations_end": "2026-10-10T23:59:00+00:00",
                            "is_online": True,
                            "apply_mode": "online",
                            "city": "Bengaluru",
                            "state": "Karnataka",
                            "country": "India",
                            "location": "Online / Virtual",
                            "team_min": 2,
                            "team_size": 4,
                            "themes": [{"name": "AI"}, {"name": "Blockchain"}],
                            "hashtags": ["web3", "machine-learning"],
                            "prizes": [
                                {"name": "Grand Prize", "desc": "100,000 INR cash prize"},
                            ],
                        }
                    }
                ],
            }
        }
        mock_post.return_value = Response(
            status_code=200,
            json=updated_payload,
            request=Request("POST", "https://api.devfolio.co/api/search/hackathons"),
        )

        async with self.session_factory() as session:
            await poll_source("devfolio", session)

        async with self.session_factory() as session:
            cs_stmt = select(ChangeSet).where(ChangeSet.opportunity_id == opp_id)
            changesets = (await session.execute(cs_stmt)).scalars().all()
            self.assertGreaterEqual(len(changesets), 1, "ChangeSet must be created on deadline update")

            deadline_cs = [c for c in changesets if c.field_name == "deadline_date"]
            self.assertEqual(len(deadline_cs), 1)
            cs = deadline_cs[0]
            self.assertEqual(cs.change_type, ChangeType.DEADLINE_CHANGED.value)
            self.assertEqual(cs.importance, PriorityLevel.CRITICAL.value)
            self.assertIn("2026-09-28", cs.previous_value)
            self.assertIn("2026-10-10", cs.new_value)

    # =========================================================================
    # TEST 8: Connector Failure Marks ScheduledJob and Increments Counters
    # =========================================================================
    async def test_8_connector_failure_updates_job_and_source_counters(self):
        """Connector failure logs failure in ScheduledJob and increments Source failure count without crashing."""
        async with self.session_factory() as session:
            src = await ensure_devfolio_source(session)
            await session.commit()
            src_id = src.id

        # Simulate exception during ingestion pipeline processing
        with patch("services.scheduler.scheduler.IngestionPipeline") as mock_pipe_cls:
            mock_pipe = AsyncMock()
            mock_pipe.process_connector.side_effect = RuntimeError("Devfolio search API connection timeout")
            mock_pipe_cls.return_value = mock_pipe

            async with self.session_factory() as session:
                # Must not raise to caller
                await poll_source("devfolio", session)

        async with self.session_factory() as session:
            job_stmt = select(ScheduledJob).where(ScheduledJob.source_id == src_id)
            job = (await session.execute(job_stmt)).scalars().first()
            self.assertIsNotNone(job)
            self.assertEqual(job.status, ScheduledJobStatus.FAILURE.value)
            self.assertIn("connection timeout", job.error_message)

            src_stmt = select(Source).where(Source.id == src_id)
            updated_src = (await session.execute(src_stmt)).scalar_one()
            self.assertEqual(updated_src.consecutive_failures, 1)
            self.assertEqual(updated_src.failure_count, 1)
            self.assertIn("connection timeout", updated_src.last_error)

    # =========================================================================
    # TEST 9: Scheduler Disabled Source Not Polled By Coordinator
    # =========================================================================
    async def test_9_scheduler_disabled_source_not_polled(self):
        """When Source.scheduler_enabled=False, coordinator ignores the source even if last_polled_at is stale."""
        now = datetime.now(timezone.utc)
        async with self.session_factory() as session:
            devfolio_src = await ensure_devfolio_source(session)
            devfolio_src.scheduler_enabled = False
            devfolio_src.last_polled_at = now - timedelta(days=5)
            await session.commit()

        polled_slugs = []

        async def fake_poll_source(slug: str, db: AsyncSession):
            polled_slugs.append(slug)

        with patch("services.scheduler.scheduler.AsyncSessionLocal", self.session_factory):
            with patch("services.scheduler.scheduler.poll_source", fake_poll_source):
                await coordinator_job(self.app)

        self.assertNotIn("devfolio", polled_slugs)


if __name__ == "__main__":
    unittest.main()
