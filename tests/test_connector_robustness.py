"""
Unit & Integration Tests for Priority 6: Connector Robustness & Failure Isolation
Validates:
- ResilientHTTPClient exponential backoff and Retry-After header parsing on 429
- ResilientHTTPClient retries on transient 5xx server errors
- Source health degradation on consecutive connector failures (HEALTHY -> DEGRADED -> FAILING)
- Individual item parsing failure isolation (malformed items do not prevent valid items from saving)
"""
import asyncio
from datetime import datetime, timezone
from pathlib import Path
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select

from apps.api.models.base import Base
from apps.api.models.discovery import RawDiscovery
from apps.api.models.opportunity import Opportunity
from apps.api.models.source import Source
from connectors.base_connector import BaseConnector, RawItem
from services.ingestion.http_client import ResilientHTTPClient
from services.ingestion.pipeline import IngestionPipeline
from shared.constants import OpportunityCategory, SourceHealthStatus, SourceType, TrustLevel


class FailingConnector(BaseConnector):
    """Test connector that simulates network or upstream failure."""
    def __init__(self, should_fail: bool = True):
        super().__init__(
            name="Failing Source",
            category=OpportunityCategory.HACKATHON,
            source_type=SourceType.API,
            trust_level=TrustLevel.HIGH,
            base_url="https://failing.example.com",
            is_active=True,
        )
        self.should_fail = should_fail

    async def health_check(self) -> bool:
        return not self.should_fail

    async def fetch_raw_items(self):
        if self.should_fail:
            raise httpx.ConnectError("Failed to reach upstream server")
        return []


class MixedItemConnector(BaseConnector):
    """Test connector that yields both valid and broken items."""
    def __init__(self):
        super().__init__(
            name="Mixed Source",
            category=OpportunityCategory.HACKATHON,
            source_type=SourceType.API,
            trust_level=TrustLevel.HIGH,
            base_url="https://mixed.example.com",
            is_active=True,
        )

    async def health_check(self) -> bool:
        return True

    async def fetch_raw_items(self):
        return [
            RawItem(
                source_name="mixed",
                title="Broken Item",
                url="https://mixed.example.com/broken",
                content="Broken content",
                source_identifier="broken-1",
            ),
            RawItem(
                source_name="mixed",
                title="Hackathon 2026: Registration Live",
                url="https://mixed.example.com/valid",
                content="Hackathon 2026 registration is live for developers. Submit project proposals before deadline. Hackathon contest with cash prizes.",
                source_identifier="valid-1",
            ),
        ]


class TestConnectorRobustness(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        self.session_factory = async_sessionmaker(
            bind=self.engine, class_=AsyncSession, expire_on_commit=False
        )

    async def asyncTearDown(self):
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await self.engine.dispose()

    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_resilient_http_client_retry_after_header(self, mock_sleep):
        """ResilientHTTPClient respects Retry-After header on 429 response."""
        resp_429 = httpx.Response(
            status_code=429,
            headers={"Retry-After": "5"},
            request=httpx.Request("GET", "https://api.example.com/data"),
        )
        resp_200 = httpx.Response(
            status_code=200,
            text='{"status": "ok"}',
            request=httpx.Request("GET", "https://api.example.com/data"),
        )

        with patch.object(httpx.AsyncClient, "get", side_effect=[resp_429, resp_200]):
            client = ResilientHTTPClient(timeout=5.0, max_retries=3)
            res = await client.get("https://api.example.com/data")
            self.assertEqual(res.status_code, 200)
            # Verify sleep was called with at least 5.0 seconds
            mock_sleep.assert_called_with(5.0)

    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_resilient_http_client_transient_503_retry(self, mock_sleep):
        """ResilientHTTPClient retries on transient 503 Service Unavailable."""
        resp_503 = httpx.Response(
            status_code=503,
            request=httpx.Request("GET", "https://api.example.com/data"),
        )
        resp_200 = httpx.Response(
            status_code=200,
            text='{"status": "ok"}',
            request=httpx.Request("GET", "https://api.example.com/data"),
        )

        with patch.object(httpx.AsyncClient, "get", side_effect=[resp_503, resp_200]):
            client = ResilientHTTPClient(timeout=5.0, max_retries=3)
            res = await client.get("https://api.example.com/data")
            self.assertEqual(res.status_code, 200)
            mock_sleep.assert_called_once()

    async def test_connector_failure_updates_source_health(self):
        """Connector failure increments consecutive_failures and sets health to FAILING."""
        connector = FailingConnector(should_fail=True)

        async with self.session_factory() as session:
            pipeline = IngestionPipeline(session)

            # Fail 5 times in a row
            for _ in range(5):
                try:
                    await pipeline.process_connector(connector)
                except httpx.ConnectError:
                    pass

            src_stmt = select(Source).where(Source.name == "Failing Source")
            src = (await session.execute(src_stmt)).scalars().first()
            self.assertIsNotNone(src)
            self.assertEqual(src.consecutive_failures, 5)
            self.assertEqual(src.status, SourceHealthStatus.FAILING.value)
            self.assertIn("Failed to reach upstream server", src.last_error)

    async def test_item_failure_isolation(self):
        """A failure in processing one item does not prevent other valid items from saving."""
        connector = MixedItemConnector()

        async with self.session_factory() as session:
            pipeline = IngestionPipeline(session)

            # Mock process_raw_item to raise an exception on the broken item
            original_process = pipeline.process_raw_item

            async def side_effect(item, **kwargs):
                if item.title == "Broken Item":
                    raise ValueError("Simulated parsing crash on malformed item")
                return await original_process(item, **kwargs)

            with patch.object(pipeline, "process_raw_item", side_effect=side_effect):
                opps = await pipeline.process_connector(connector)

            # Valid item should have succeeded
            self.assertEqual(len(opps), 1)
            self.assertIn("Hackathon 2026", opps[0].title)

            # Source remains healthy
            src = (await session.execute(select(Source).where(Source.name == "Mixed Source"))).scalars().first()
            self.assertEqual(src.status, SourceHealthStatus.HEALTHY.value)
            self.assertEqual(src.consecutive_failures, 0)
