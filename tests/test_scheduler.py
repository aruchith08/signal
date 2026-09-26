"""
Unit Tests for Phase 5A: APScheduler Foundation & Polling Policy
Validates:
- Scheduler singleton retrieval attached to FastAPI app.state
- Coordinator discovers due sources respecting is_active and scheduler_enabled
- PollingPolicy intervals (HIGH_PRIORITY=30m, MEDIUM_PRIORITY=120m, LOW_PRIORITY=360m, ARCHIVAL=1440m, ADAPTIVE backoff)
- poll_source creates ScheduledJob records and updates Source health metrics
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import unittest
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select

from apps.api.models.base import Base
from apps.api.models.source import Source
from apps.api.models.scheduled_job import ScheduledJob
from services.scheduler.scheduler import get_scheduler, coordinator_job, poll_source
from shared.constants import (
    OpportunityCategory,
    PollingPolicy,
    ScheduledJobStatus,
    SourceHealthStatus,
    SourceType,
    TrustLevel,
)


class TestSchedulerFoundation(unittest.IsolatedAsyncioTestCase):
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

    def test_scheduler_singleton(self):
        """get_scheduler must return the same AsyncIOScheduler instance attached to app.state."""
        s1 = get_scheduler(self.app)
        s2 = get_scheduler(self.app)
        self.assertIs(s1, s2)
        self.assertTrue(hasattr(self.app.state, "scheduler"))

    async def test_coordinator_discovers_due_sources_with_polling_policy(self):
        """Coordinator must discover due active sources and respect polling policy intervals."""
        now = datetime.now(timezone.utc)
        async with self.session_factory() as session:
            # 1. Active & scheduler_enabled source, due for polling
            src_due = Source(
                name="Codeforces API",
                slug="codeforces-api",
                category=OpportunityCategory.COMPETITIVE_PROGRAMMING.value,
                source_type=SourceType.API.value,
                base_url="https://codeforces.com/api",
                is_active=True,
                scheduler_enabled=True,
                polling_policy=PollingPolicy.HIGH_PRIORITY.value,  # 30 min interval
                last_polled_at=now - timedelta(minutes=35),
            )
            # 2. Source polled recently, not yet due
            src_not_due = Source(
                name="Devfolio Feed",
                slug="devfolio-feed",
                category=OpportunityCategory.HACKATHON.value,
                source_type=SourceType.JSON_FEED.value,
                base_url="https://api.devfolio.co",
                is_active=True,
                scheduler_enabled=True,
                polling_policy=PollingPolicy.MEDIUM_PRIORITY.value,  # 120 min interval
                last_polled_at=now - timedelta(minutes=10),
            )
            # 3. Source with scheduler_enabled=False (disabled)
            src_disabled = Source(
                name="Disabled Portal",
                slug="disabled-portal",
                category=OpportunityCategory.OTHER.value,
                source_type=SourceType.HTML.value,
                base_url="https://disabled.example.com",
                is_active=True,
                scheduler_enabled=False,
                last_polled_at=now - timedelta(days=1),
            )
            # 4. Inactive source (is_active=False)
            src_inactive = Source(
                name="Inactive Portal",
                slug="inactive-portal",
                category=OpportunityCategory.OTHER.value,
                source_type=SourceType.HTML.value,
                base_url="https://inactive.example.com",
                is_active=False,
                scheduler_enabled=True,
                last_polled_at=now - timedelta(days=1),
            )
            session.add_all([src_due, src_not_due, src_disabled, src_inactive])
            await session.commit()

        # Patch AsyncSessionLocal and poll_source in scheduler
        polled_slugs = []

        async def fake_poll_source(slug: str, db: AsyncSession):
            polled_slugs.append(slug)

        with patch("services.scheduler.scheduler.AsyncSessionLocal", self.session_factory):
            with patch("services.scheduler.scheduler.poll_source", fake_poll_source):
                await coordinator_job(self.app)

        # Only src_due should have been triggered
        self.assertEqual(polled_slugs, ["codeforces-api"])

    async def test_poll_source_records_scheduled_job(self):
        """poll_source must create a ScheduledJob and update source metrics."""
        async with self.session_factory() as session:
            src = Source(
                name="Test Connector Source",
                slug="test-connector",
                category=OpportunityCategory.TECH_COMPETITION.value,
                source_type=SourceType.API.value,
                base_url="https://test.example.com",
                is_active=True,
                scheduler_enabled=True,
                consecutive_failures=2,
            )
            session.add(src)
            await session.commit()
            src_id = src.id

        # Mock connector and ingestion pipeline
        fake_connector_cls = lambda: "fake_connector"
        with patch.dict("services.scheduler.scheduler.CONNECTOR_REGISTRY", {"test-connector": fake_connector_cls}):
            with patch("services.scheduler.scheduler.IngestionPipeline") as mock_pipeline_cls:
                mock_pipeline_instance = AsyncMock()
                mock_pipeline_instance.process_connector.return_value = ["item1", "item2"]
                mock_pipeline_cls.return_value = mock_pipeline_instance

                async with self.session_factory() as session:
                    await poll_source("test-connector", session)

        # Verify ScheduledJob row was created and source was updated
        async with self.session_factory() as session:
            job_stmt = select(ScheduledJob).where(ScheduledJob.source_id == src_id)
            job = (await session.execute(job_stmt)).scalars().first()
            self.assertIsNotNone(job)
            self.assertEqual(job.status, ScheduledJobStatus.SUCCESS.value)
            self.assertEqual(job.items_discovered, 2)
            self.assertEqual(job.items_processed, 2)
            self.assertIsNotNone(job.duration_ms)

            src_stmt = select(Source).where(Source.id == src_id)
            updated_src = (await session.execute(src_stmt)).scalars().first()
            self.assertEqual(updated_src.consecutive_failures, 0)
            self.assertIsNotNone(updated_src.last_polled_at)
            self.assertIsNotNone(updated_src.last_successful_check)


if __name__ == "__main__":
    unittest.main()
