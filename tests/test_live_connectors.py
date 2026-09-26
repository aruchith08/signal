"""
Unit & Integration Tests for SIGNAL Phase 1A Live Connectors & Ingestion Audit
Verifies Codeforces, GitHub Blog, and SIH connectors, RawDiscovery tracking, and API endpoints.
All tests are mock-safe (no live internet dependency in test suite).
"""
import json
from datetime import datetime, timezone
from pathlib import Path
import sys
import unittest
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from httpx import Response, AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select

from apps.api.database import get_db, Base
from apps.api.main import app
from apps.api.models import Opportunity, Organization, Source
from apps.api.models.discovery import RawDiscovery
from connectors.competitive_programming.codeforces import CodeforcesConnector
from connectors.companies.github_blog import GitHubBlogConnector
from connectors.government.sih import SIHConnector
from services.ingestion.pipeline import IngestionPipeline
from shared.constants import DiscoveryStatus, OpportunityCategory, SourceType


SAMPLE_CODEFORCES_JSON = {
    "status": "OK",
    "result": [
        {
            "id": 2085,
            "name": "Codeforces Round 1009 (Div. 2)",
            "type": "CF",
            "phase": "BEFORE",
            "frozen": False,
            "durationSeconds": 7200,
            "startTimeSeconds": 1742051100,
            "relativeTimeSeconds": -12345,
        },
        {
            "id": 2084,
            "name": "Codeforces Round 1008 (Div. 1)",
            "type": "CF",
            "phase": "FINISHED",
            "frozen": False,
            "durationSeconds": 7200,
            "startTimeSeconds": 1741000000,
            "relativeTimeSeconds": 10000,
        },
    ],
}

SAMPLE_GITHUB_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>The GitHub Blog</title>
    <link>https://github.blog</link>
    <description>Updates and news from GitHub</description>
    <item>
      <title>GitHub Global Student Hackathon &amp; Fellowship Announcement</title>
      <link>https://github.blog/2026-09-01-student-fellowship-hackathon/</link>
      <guid>https://github.blog/?p=123456</guid>
      <pubDate>Mon, 01 Sep 2026 12:00:00 +0000</pubDate>
      <category><![CDATA[Students]]></category>
      <category><![CDATA[Open Source]]></category>
      <description><![CDATA[<p>We are thrilled to launch the 2026 Global Student Fellowship with grants and mentorship.</p>]]></description>
    </item>
  </channel>
</rss>
"""

SAMPLE_SIH_HTML = """<!DOCTYPE html>
<html>
<body>
<div class="container">
    <div id="ViewProblemStatement26001" class="modal fade" role="dialog">
        <table>
            <tr><th>Problem Statement ID</th><td>26001</td></tr>
            <tr><th>Problem Statement Title</th><td>AI-Based Early Warning &amp; Disaster Monitoring</td></tr>
            <tr><th>Organization</th><td>Ministry of Development of North Eastern Region</td></tr>
            <tr><th>Department</th><td>Disaster Management Cell</td></tr>
            <tr><th>Category</th><td>Software</td></tr>
            <tr><th>Theme</th><td>Disaster Management</td></tr>
            <tr><th>Description</th><td>Build an AI predictive system for flood and landslide monitoring across regions.</td></tr>
        </table>
    </div>
</div>
</body>
</html>
"""


class TestLiveConnectors(unittest.IsolatedAsyncioTestCase):
    """Test suite for live connector parsers and data normalizers."""

    @patch("services.ingestion.http_client.ResilientHTTPClient.get")
    async def test_codeforces_connector_parsing(self, mock_get):
        mock_resp = Response(
            status_code=200,
            json=SAMPLE_CODEFORCES_JSON,
            request=AsyncMock(),
        )
        mock_get.return_value = mock_resp

        connector = CodeforcesConnector(include_recent_finished=5)
        self.assertTrue(await connector.health_check())

        items = await connector.fetch_raw_items()
        self.assertEqual(len(items), 2)

        # First item (Upcoming Div. 2 contest)
        first = items[0]
        self.assertEqual(first.title, "Codeforces Round 1009 (Div. 2)")
        self.assertEqual(first.url, "https://codeforces.com/contest/2085")
        self.assertEqual(first.source_name, "Codeforces")
        self.assertEqual(first.source_identifier, "2085")
        self.assertIn("Phase: BEFORE", first.content)
        self.assertIn("2.0 hours", first.content)
        self.assertEqual(first.metadata["contest_id"], 2085)
        self.assertEqual(first.metadata["phase"], "BEFORE")

    @patch("services.ingestion.http_client.ResilientHTTPClient.get")
    async def test_github_blog_connector_parsing(self, mock_get):
        mock_resp = Response(
            status_code=200,
            content=SAMPLE_GITHUB_RSS.encode("utf-8"),
            request=AsyncMock(),
        )
        mock_get.return_value = mock_resp

        connector = GitHubBlogConnector()
        self.assertTrue(await connector.health_check())

        items = await connector.fetch_raw_items()
        self.assertEqual(len(items), 1)

        item = items[0]
        self.assertIn("Student Hackathon & Fellowship", item.title)
        self.assertEqual(item.url, "https://github.blog/2026-09-01-student-fellowship-hackathon/")
        self.assertEqual(item.source_name, "GitHub Blog")
        self.assertIn("Open Source", item.metadata["categories"])
        self.assertIn("Students", item.metadata["categories"])
        self.assertIsNotNone(item.published_at)
        self.assertEqual(item.published_at.year, 2026)

    @patch("services.ingestion.http_client.ResilientHTTPClient.get")
    async def test_sih_connector_parsing(self, mock_get):
        mock_resp = Response(
            status_code=200,
            text=SAMPLE_SIH_HTML,
            request=AsyncMock(),
        )
        mock_get.return_value = mock_resp

        connector = SIHConnector()
        items = await connector.fetch_raw_items()
        self.assertEqual(len(items), 1)

        item = items[0]
        self.assertEqual(item.source_identifier, "26001")
        self.assertIn("AI-Based Early Warning", item.title)
        self.assertIn("Ministry of Development of North Eastern Region", item.content)
        self.assertEqual(item.metadata["category"], "Software")
        self.assertEqual(item.metadata["theme"], "Disaster Management")


class TestPipelineWithLiveConnectors(unittest.IsolatedAsyncioTestCase):
    """Verifies end-to-end ingestion pipeline with RawDiscovery tracking."""

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

    @patch("services.ingestion.http_client.ResilientHTTPClient.get")
    async def test_codeforces_pipeline_ingestion(self, mock_get):
        """Verify Codeforces items are audited in raw_discoveries and ingested into opportunities."""
        mock_resp = Response(status_code=200, json=SAMPLE_CODEFORCES_JSON, request=AsyncMock())
        mock_get.return_value = mock_resp

        async with self.session_factory() as session:
            pipeline = IngestionPipeline(session)
            connector = CodeforcesConnector()
            opportunities = await pipeline.process_connector(connector)

            self.assertGreaterEqual(len(opportunities), 1)

            # Check raw_discoveries audit records
            stmt_disc = select(RawDiscovery).order_by(RawDiscovery.created_at)
            discoveries = (await session.execute(stmt_disc)).scalars().all()
            self.assertEqual(len(discoveries), 2)
            self.assertTrue(all(d.status == DiscoveryStatus.PROCESSED.value for d in discoveries))
            self.assertTrue(all(d.opportunity_id is not None for d in discoveries))

            # Check Source record was auto-created and updated
            stmt_source = select(Source).where(Source.slug == "codeforces")
            source = (await session.execute(stmt_source)).scalars().first()
            self.assertIsNotNone(source)
            self.assertIsNotNone(source.last_polled_at)
            self.assertEqual(source.failure_count, 0)

    @patch("services.ingestion.http_client.ResilientHTTPClient.get")
    async def test_repeated_pipeline_run_creates_no_duplicates(self, mock_get):
        """Verify repeated connector execution is completely idempotent."""
        mock_resp = Response(status_code=200, json=SAMPLE_CODEFORCES_JSON, request=AsyncMock())
        mock_get.return_value = mock_resp

        async with self.session_factory() as session:
            pipeline = IngestionPipeline(session)
            connector = CodeforcesConnector()

            # First run
            run1 = await pipeline.process_connector(connector)
            self.assertGreaterEqual(len(run1), 1)

            # Second run
            run2 = await pipeline.process_connector(connector)
            self.assertEqual(len(run1), len(run2))

            # Database should have exactly the original count
            stmt = select(Opportunity)
            all_opps = (await session.execute(stmt)).scalars().all()
            self.assertEqual(len(all_opps), len(run1))


class TestDiscoveriesAndIngestionAPI(unittest.IsolatedAsyncioTestCase):
    """Test Discoveries and Ingestion API endpoints."""

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

    async def test_list_connectors_api(self):
        """Verify GET /api/v1/ingestion/connectors lists registered connectors."""
        async with AsyncClient(transport=self.transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/ingestion/connectors")
            self.assertEqual(resp.status_code, 200)
            connectors = resp.json()
            slugs = [c["slug"] for c in connectors]
            self.assertIn("codeforces", slugs)
            self.assertIn("github-blog", slugs)
            self.assertIn("smart-india-hackathon", slugs)

    @patch("services.ingestion.http_client.ResilientHTTPClient.get")
    async def test_trigger_live_and_discoveries_audit_api(self, mock_get):
        """Verify POST /api/v1/ingestion/trigger-live/{slug} and GET /api/v1/discoveries."""
        mock_resp = Response(status_code=200, json=SAMPLE_CODEFORCES_JSON, request=AsyncMock())
        mock_get.return_value = mock_resp

        async with AsyncClient(transport=self.transport, base_url="http://test") as client:
            # Trigger live ingestion
            resp = await client.post("/api/v1/ingestion/trigger-live/codeforces")
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertEqual(data["status"], "completed")
            self.assertGreaterEqual(data["total_opportunities_created"], 1)

            # Query discoveries API
            disc_resp = await client.get("/api/v1/discoveries")
            self.assertEqual(disc_resp.status_code, 200)
            disc_data = disc_resp.json()
            self.assertGreaterEqual(disc_data["total"], 1)
            first_disc = disc_data["items"][0]
            self.assertEqual(first_disc["status"], "processed")
            self.assertIsNotNone(first_disc["opportunity_id"])

            # Query single discovery by ID
            single_resp = await client.get(f"/api/v1/discoveries/{first_disc['id']}")
            self.assertEqual(single_resp.status_code, 200)
            self.assertEqual(single_resp.json()["id"], first_disc["id"])


if __name__ == "__main__":
    unittest.main()
