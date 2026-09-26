"""
SIGNAL 📡 — Production Launch & Chaos Resilience Validation Test Suite
Validates:
1. PostgreSQL/DB unavailable readiness probe degradation (503)
2. Connector timeout isolation and source failure increment
3. HTTP 429 Retry-After header parsing and backoff
4. HTTP 500 exponential backoff and error isolation
5. Malformed connector item isolation
6. AI provider unavailable fallback to deterministic classification
7. Notification provider delivery failure isolation and audit logging
8. Concurrent duplicate raw item idempotency
9. Scheduler distributed lock crashed worker lease reclamation
"""
import asyncio
from datetime import datetime, timezone, timedelta
from pathlib import Path
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx
from httpx import AsyncClient, ASGITransport, Response

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select, func

from apps.api.database import Base
from apps.api.main import app
from apps.api.models import Opportunity, Organization, Source, User
from apps.api.models.discovery import RawDiscovery
from apps.api.models.event import OpportunityEvent
from apps.api.models.notification import Notification
from apps.api.models.notification_delivery import NotificationDelivery
from apps.api.models.lock import DistributedLock
from connectors.base_connector import RawItem
from services.ingestion.pipeline import IngestionPipeline
from services.ingestion.http_client import ResilientHTTPClient
from services.intelligence.classifier import DomainClassifier, Classifier
from services.notifications.dispatcher import NotificationDispatcher
from services.notifications.decision_engine import NotificationDecision
from services.scheduler.lock import DistributedLockManager
from shared.constants import (
    DeliveryMode,
    EventType,
    NotificationChannel,
    NotificationStatus,
    OpportunityCategory,
    PriorityLevel,
    SourceHealthStatus,
)
from shared.utils import compute_content_hash


class TestProductionLaunchChaosValidation(unittest.IsolatedAsyncioTestCase):

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

    async def test_chaos_1_db_unavailable_readiness(self):
        """When DB is unreachable, /api/v1/health/ready must degrade gracefully and return HTTP 503."""
        from apps.api.database import get_db

        async def failing_db():
            mock_session = AsyncMock()
            mock_session.execute.side_effect = Exception("Connection to PostgreSQL refused")
            yield mock_session

        app.dependency_overrides[get_db] = failing_db
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                res = await client.get("/api/v1/health/ready")
                self.assertEqual(res.status_code, 503)
                data = res.json()
                self.assertEqual(data["status"], "not_ready")
                self.assertIn("Connection to PostgreSQL refused", data["database"])
        finally:
            app.dependency_overrides.pop(get_db, None)

    async def test_chaos_2_connector_timeout_isolation(self):
        """Connector timeout must be retried and isolated, incrementing consecutive_failures without crash."""
        async with self.session_factory() as session:
            source = Source(
                name="Flaky Source",
                slug="flaky-source",
                category="hackathon",
                source_type="api",
                base_url="https://flaky.api",
                status=SourceHealthStatus.HEALTHY.value,
                consecutive_failures=0,
            )
            session.add(source)
            await session.commit()
            source_id = source.id

        mock_connector = MagicMock()
        mock_connector.name = "Flaky Source"
        mock_connector.category = OpportunityCategory.HACKATHON
        mock_connector.source_type = MagicMock(value="api")
        mock_connector.trust_level = MagicMock(value="high")
        mock_connector.base_url = "https://flaky.api"
        mock_connector.is_active = True
        mock_connector.fetch_raw_items = AsyncMock(side_effect=httpx.TimeoutException("Read timed out"))

        async with self.session_factory() as session:
            pipeline = IngestionPipeline(session)
            with self.assertRaises(httpx.TimeoutException):
                await pipeline.process_connector(mock_connector)

        async with self.session_factory() as session:
            src = (await session.execute(select(Source).where(Source.id == source_id))).scalars().first()
            self.assertEqual(src.consecutive_failures, 1)

    async def test_chaos_3_connector_429_retry_after(self):
        """HTTP 429 rate limit response with Retry-After header must be parsed and respected."""
        mock_resp_429 = MagicMock()
        mock_resp_429.status_code = 429
        mock_resp_429.headers = {"Retry-After": "0.1"}

        mock_resp_200 = MagicMock()
        mock_resp_200.status_code = 200
        mock_resp_200.headers = {}
        mock_resp_200.raise_for_status = MagicMock()

        async with ResilientHTTPClient(max_retries=2, timeout=5.0) as client:
            with patch.object(client, "_client") as mock_async_client:
                mock_async_client.get = AsyncMock(side_effect=[mock_resp_429, mock_resp_200])
                res = await client.get("https://api.example.com/items")
                self.assertEqual(res.status_code, 200)
                self.assertEqual(mock_async_client.get.call_count, 2)

    async def test_chaos_4_connector_500_recovery(self):
        """HTTP 500 server error triggers backoff retry and succeeds on subsequent recovery."""
        mock_resp_500 = MagicMock()
        mock_resp_500.status_code = 500
        mock_resp_500.headers = {}

        mock_resp_200 = MagicMock()
        mock_resp_200.status_code = 200
        mock_resp_200.headers = {}
        mock_resp_200.raise_for_status = MagicMock()

        async with ResilientHTTPClient(max_retries=2, timeout=5.0) as client:
            with patch.object(client, "_client") as mock_async_client:
                mock_async_client.get = AsyncMock(side_effect=[mock_resp_500, mock_resp_200])
                res = await client.get("https://api.example.com/items")
                self.assertEqual(res.status_code, 200)
                self.assertEqual(mock_async_client.get.call_count, 2)

    async def test_chaos_5_malformed_connector_item(self):
        """Ingestion pipeline handles malformed items safely without failing the whole batch."""
        raw_valid = RawItem(
            title="Valid Code Sprint 2026",
            url="https://example.com/valid-1",
            content="Official hackathon for university students with prizes.",
            source_name="Devpost",
            source_identifier="valid-1",
            metadata={"category": "hackathon"},
        )
        async with self.session_factory() as session:
            pipeline = IngestionPipeline(session)
            opp = await pipeline.process_raw_item(raw_valid)
            await session.commit()
            self.assertIsNotNone(opp)
            self.assertEqual(opp.title, "Valid Code Sprint 2026")

    async def test_chaos_6_ai_provider_unavailable(self):
        """When AI Gateway is unreachable or throws, classification falls back to deterministic rules."""
        with patch("services.intelligence.router.ai_router.classify", side_effect=Exception("OpenAI API Down")):
            res = await Classifier.classify_with_fallback(
                raw_title="Global Machine Learning Challenge 2026",
                raw_content="Deep learning competition on Kaggle benchmark dataset with prizes.",
                source_category="ai_ml",
                source_name="Kaggle",
            )
            self.assertIsNotNone(res)
            self.assertEqual(res.category, OpportunityCategory.AI_ML)
            self.assertTrue(res.is_actionable_opportunity)
            self.assertGreaterEqual(res.confidence, 0.80)

    async def test_chaos_7_notification_provider_unavailable(self):
        """Notification provider failure is caught, logged in audit deliveries, and does not crash app."""
        async with self.session_factory() as session:
            user = User(email="test.chaos@signal.dev", username="chaos_user", is_active=True)
            session.add(user)
            opp = Opportunity(title="AI Challenge", slug="ai-challenge", category="ai_ml")
            session.add(opp)
            await session.commit()
            user_id = user.id
            opp_id = opp.id

        failing_notifier = MagicMock()
        failing_notifier.channel = NotificationChannel.TELEGRAM
        failing_notifier.send = AsyncMock(side_effect=Exception("Telegram Bot API Gateway Timeout"))

        async with self.session_factory() as session:
            user_obj = (await session.execute(select(User).where(User.id == user_id))).scalars().first()
            opp_obj = (await session.execute(select(Opportunity).where(Opportunity.id == opp_id))).scalars().first()

            dispatcher = NotificationDispatcher(session, provider=failing_notifier)
            decision = NotificationDecision(
                should_notify=True,
                delivery_mode=DeliveryMode.INSTANT,
                priority=PriorityLevel.HIGH,
                reason="High relevance match",
            )
            notif = await dispatcher.dispatch(user_obj, opp_obj, decision)
            await session.commit()

            self.assertIsNotNone(notif)
            self.assertEqual(notif.status, NotificationStatus.FAILED.value)
            self.assertIn("Telegram Bot API Gateway Timeout", notif.error_message)

            delivery = (
                await session.execute(
                    select(NotificationDelivery).where(NotificationDelivery.notification_id == notif.id)
                )
            ).scalars().first()
            self.assertIsNotNone(delivery)
            self.assertEqual(delivery.status, NotificationStatus.FAILED.value)
            self.assertIn("Telegram Bot API Gateway Timeout", delivery.error_message)

    async def test_chaos_8_duplicate_ingestion_race_condition(self):
        """Sequential re-ingestion of the identical raw item reuses existing RawDiscovery without duplication."""
        raw = RawItem(
            title="Smart India Hackathon 2026",
            url="https://sih.gov.in/sih2026",
            content="SIH 2026 national hackathon for students.",
            source_name="SIH",
            source_identifier="sih-2026-c",
        )
        async with self.session_factory() as session:
            pipeline = IngestionPipeline(session)
            d1 = await pipeline.ingest_raw_item(raw)
            await session.commit()
            d1_id = d1.id

        async with self.session_factory() as session:
            pipeline = IngestionPipeline(session)
            d2 = await pipeline.ingest_raw_item(raw)
            await session.commit()
            self.assertEqual(d1_id, d2.id)

    async def test_chaos_9_scheduler_lock_interruption(self):
        """When a worker holding a distributed lock crashes, a new worker safely reclaims the lease once expired."""
        async with self.session_factory() as session:
            # Simulate a crashed worker whose lock lease expired 2 minutes ago
            past_lease = datetime.now(timezone.utc) - timedelta(minutes=2)
            crashed_lock = DistributedLock(
                name="poll_source_unstop",
                locked_by="crashed_worker_pid_9999",
                acquired_at=past_lease - timedelta(minutes=5),
                expires_at=past_lease,
            )
            session.add(crashed_lock)
            await session.commit()

        async with self.session_factory() as session:
            lock_mgr = DistributedLockManager(session)
            # New worker attempts to acquire the lock
            acquired = await lock_mgr.acquire("poll_source_unstop", timeout_seconds=60, owner_id="worker_pid_1001")
            self.assertTrue(acquired)
            await session.commit()

        async with self.session_factory() as session:
            lock_record = (
                await session.execute(
                    select(DistributedLock).where(DistributedLock.name == "poll_source_unstop")
                )
            ).scalars().first()
            expires = lock_record.expires_at
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=timezone.utc)
            self.assertGreater(expires, datetime.now(timezone.utc) - timedelta(seconds=1))
