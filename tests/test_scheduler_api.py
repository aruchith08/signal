"""
Unit and Integration Tests for Phase 5A: Scheduler Observability API
Validates:
- GET /api/v1/scheduler/status
- GET /api/v1/scheduler/jobs (pagination, ordering, filtering)
- POST /api/v1/scheduler/poll/{source_slug} (success and 404 handling)
- POST /api/v1/scheduler/poll-all (triggers only active + scheduler_enabled sources)
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import unittest
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from apps.api.database import Base, get_db
from apps.api.main import app
from apps.api.models.source import Source
from apps.api.models.scheduled_job import ScheduledJob
from shared.constants import (
    OpportunityCategory,
    PollingPolicy,
    ScheduledJobStatus,
    SourceType,
)


class TestSchedulerAPI(unittest.IsolatedAsyncioTestCase):
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

        # Seed test sources
        now = datetime.now(timezone.utc)
        async with self.session_factory() as session:
            self.src_active = Source(
                name="Codeforces API",
                slug="codeforces-api",
                category=OpportunityCategory.COMPETITIVE_PROGRAMMING.value,
                source_type=SourceType.API.value,
                base_url="https://codeforces.com/api",
                is_active=True,
                scheduler_enabled=True,
                polling_policy=PollingPolicy.HIGH_PRIORITY.value,
                last_polled_at=now - timedelta(hours=2),
            )
            self.src_disabled = Source(
                name="Disabled Source",
                slug="disabled-source",
                category=OpportunityCategory.OTHER.value,
                source_type=SourceType.HTML.value,
                base_url="https://disabled.example.com",
                is_active=True,
                scheduler_enabled=False,
            )
            self.src_inactive = Source(
                name="Inactive Source",
                slug="inactive-source",
                category=OpportunityCategory.OTHER.value,
                source_type=SourceType.HTML.value,
                base_url="https://inactive.example.com",
                is_active=False,
                scheduler_enabled=True,
            )
            session.add_all([self.src_active, self.src_disabled, self.src_inactive])
            await session.commit()
            self.active_source_id = self.src_active.id

            # Seed a ScheduledJob for testing /jobs
            self.job1 = ScheduledJob(
                source_id=self.active_source_id,
                started_at=now - timedelta(minutes=45),
                finished_at=now - timedelta(minutes=44),
                duration_ms=60000,
                status=ScheduledJobStatus.SUCCESS.value,
                items_discovered=5,
                items_processed=5,
            )
            self.job2 = ScheduledJob(
                source_id=self.active_source_id,
                started_at=now - timedelta(minutes=15),
                finished_at=now - timedelta(minutes=14),
                duration_ms=60000,
                status=ScheduledJobStatus.FAILURE.value,
                error_message="Connection reset by peer",
            )
            session.add_all([self.job1, self.job2])
            await session.commit()

    async def asyncTearDown(self):
        app.dependency_overrides.clear()
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await self.engine.dispose()

    async def test_get_scheduler_status(self):
        """GET /api/v1/scheduler/status must return operational metrics and source counts."""
        async with AsyncClient(transport=self.transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/scheduler/status")
            self.assertEqual(resp.status_code, 200)
            data = resp.json()

            self.assertIn("running", data)
            self.assertIn("timezone", data)
            self.assertIn("scheduler_jobs_count", data)
            self.assertEqual(data["sources"]["total"], 3)
            self.assertEqual(data["sources"]["active"], 2)
            self.assertEqual(data["sources"]["scheduler_enabled"], 1)
            self.assertEqual(data["sources"]["due_for_polling"], 1)
            self.assertEqual(data["recent_successful_polls_24h"], 1)
            self.assertEqual(data["recent_failed_polls_24h"], 1)

    async def test_get_scheduled_jobs(self):
        """GET /api/v1/scheduler/jobs must return paginated audit logs ordered newest first."""
        async with AsyncClient(transport=self.transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/scheduler/jobs")
            self.assertEqual(resp.status_code, 200)
            data = resp.json()

            self.assertEqual(data["total"], 2)
            self.assertEqual(len(data["items"]), 2)
            # Newest job should be first (job2 started 15 min ago vs job1 started 45 min ago)
            self.assertEqual(data["items"][0]["status"], ScheduledJobStatus.FAILURE.value)
            self.assertEqual(data["items"][1]["status"], ScheduledJobStatus.SUCCESS.value)
            self.assertEqual(data["items"][0]["source_slug"], "codeforces-api")

            # Filter by status
            resp_filter = await client.get("/api/v1/scheduler/jobs?status=success")
            self.assertEqual(resp_filter.status_code, 200)
            data_filter = resp_filter.json()
            self.assertEqual(data_filter["total"], 1)
            self.assertEqual(data_filter["items"][0]["status"], ScheduledJobStatus.SUCCESS.value)

    async def test_trigger_source_poll_success(self):
        """POST /api/v1/scheduler/poll/{slug} triggers poll_source and returns result."""
        async def mock_poll_source(source_slug: str, db: AsyncSession):
            # Simulate ScheduledJob creation
            job = ScheduledJob(
                source_id=self.active_source_id,
                started_at=datetime.now(timezone.utc),
                status=ScheduledJobStatus.SUCCESS.value,
                items_discovered=3,
                items_processed=3,
                duration_ms=1200,
            )
            db.add(job)
            await db.commit()

        with patch("apps.api.routers.scheduler.poll_source", side_effect=mock_poll_source):
            async with AsyncClient(transport=self.transport, base_url="http://test") as client:
                resp = await client.post("/api/v1/scheduler/poll/codeforces-api")
                self.assertEqual(resp.status_code, 200)
                data = resp.json()
                self.assertTrue(data["success"])
                self.assertEqual(data["source_slug"], "codeforces-api")
                self.assertEqual(data["items_discovered"], 3)
                self.assertEqual(data["status"], ScheduledJobStatus.SUCCESS.value)

    async def test_trigger_source_poll_not_found(self):
        """POST /api/v1/scheduler/poll/{slug} with unknown slug returns 404."""
        async with AsyncClient(transport=self.transport, base_url="http://test") as client:
            resp = await client.post("/api/v1/scheduler/poll/nonexistent-slug")
            self.assertEqual(resp.status_code, 404)

    async def test_trigger_poll_all_eligible(self):
        """POST /api/v1/scheduler/poll-all triggers only active & scheduler_enabled sources."""
        polled_slugs = []

        async def mock_poll_source(source_slug: str, db: AsyncSession):
            polled_slugs.append(source_slug)

        with patch("apps.api.routers.scheduler.poll_source", side_effect=mock_poll_source):
            async with AsyncClient(transport=self.transport, base_url="http://test") as client:
                resp = await client.post("/api/v1/scheduler/poll-all")
                self.assertEqual(resp.status_code, 200)
                data = resp.json()
                self.assertTrue(data["success"])
                self.assertEqual(data["total_eligible"], 1)
                self.assertEqual(data["triggered_sources"], ["codeforces-api"])
                self.assertEqual(polled_slugs, ["codeforces-api"])


if __name__ == "__main__":
    unittest.main()
