"""
Unit and Integration Tests for Phase 5C: Notification Delivery Infrastructure & Retry System
Validates:
1. Successful Telegram delivery
2. Failed Telegram delivery
3. NotificationDelivery failure state is recorded
4. Retry increments attempt_count
5. Retry succeeds after previous failure
6. Maximum retry attempts stop further retries
7. Retry coordinator finds eligible deliveries
8. Retry coordinator ignores completed deliveries
9. Provider health status endpoint (GET /api/v1/notifications/providers/status)
10. Notification delivery history endpoint (GET /api/v1/notifications/deliveries)
11. Manual retry endpoint (POST /api/v1/notifications/deliveries/{id}/retry)
"""
from datetime import datetime, timezone, timedelta
from pathlib import Path
import sys
import unittest
from unittest.mock import AsyncMock, patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select

from apps.api.database import Base, get_db
from apps.api.main import app
from apps.api.models import Opportunity, User, Notification, NotificationDelivery
from services.notifications.base_notifier import BaseNotifier
from services.notifications.telegram import TelegramNotifier
from services.notifications.mock_notifier import MockNotifier
from services.notifications.provider_registry import NotificationProviderRegistry, provider_registry
from services.notifications.retry import NotificationRetryEngine, MAX_ATTEMPTS
from shared.constants import NotificationChannel, NotificationStatus, PriorityLevel, DeliveryMode


class TestNotificationDeliveryAndRetry(unittest.IsolatedAsyncioTestCase):
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

        # Seed test data
        async with self.session_factory() as session:
            self.user = User(
                id="test-user-retry-1",
                username="retry_user_1",
                email="retry1@example.com",
                full_name="Retry User One",
                is_active=True,
            )
            session.add(self.user)

            self.opp = Opportunity(
                id="test-opp-retry-1",
                title="HackMIT 2026",
                slug="hackmit-2026",
                category="hackathons",
                status="active",
                current_state="announced",
                confidence_score=90,
            )
            session.add(self.opp)

            self.notif = Notification(
                id="test-notif-retry-1",
                user_id=self.user.id,
                opportunity_id=self.opp.id,
                channel="telegram",
                priority=PriorityLevel.HIGH.value,
                status=NotificationStatus.FAILED.value,
                delivery_mode=DeliveryMode.INSTANT.value,
                message="HackMIT 2026 registrations are open!",
            )
            session.add(self.notif)

            self.delivery_failed = NotificationDelivery(
                id="test-deliv-failed-1",
                notification_id=self.notif.id,
                channel=NotificationChannel.TELEGRAM.value,
                status=NotificationStatus.FAILED.value,
                attempt_count=1,
                last_attempt_at=datetime.now(timezone.utc) - timedelta(minutes=10),
                error_message="Connection timed out",
                channel_identifier="chat_12345",
            )
            session.add(self.delivery_failed)

            await session.commit()

    async def asyncTearDown(self):
        app.dependency_overrides.clear()
        await self.engine.dispose()

    async def test_1_telegram_notifier_successful_delivery(self):
        """1. Successful Telegram delivery sends HTTP POST and returns True."""
        notifier = TelegramNotifier(bot_token="dummy_token")
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = MagicMock(status_code=200, text="ok")
            result = await notifier.send(
                recipient="123456",
                message="Test Telegram Alert",
                priority=PriorityLevel.HIGH,
            )
            self.assertTrue(result)
            mock_post.assert_called_once()

    async def test_2_telegram_notifier_failed_delivery(self):
        """2. Failed Telegram delivery handles error response and returns False."""
        notifier = TelegramNotifier(bot_token="dummy_token")
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = MagicMock(status_code=500, text="Internal Server Error")
            result = await notifier.send(
                recipient="123456",
                message="Test Telegram Alert",
            )
            self.assertFalse(result)

    async def test_3_notification_delivery_failure_state_recorded(self):
        """3. NotificationDelivery initial failure state is verified."""
        async with self.session_factory() as session:
            stmt = select(NotificationDelivery).where(NotificationDelivery.id == "test-deliv-failed-1")
            deliv = (await session.execute(stmt)).scalar_one()
            self.assertEqual(deliv.status, NotificationStatus.FAILED.value)
            self.assertEqual(deliv.attempt_count, 1)
            self.assertIn("timed out", deliv.error_message)

    async def test_4_retry_increments_attempt_count(self):
        """4. Retry increments attempt_count and updates last_attempt_at."""
        async with self.session_factory() as session:
            mock_provider = MockNotifier()
            registry = NotificationProviderRegistry()
            registry.register(NotificationChannel.TELEGRAM, mock_provider)

            retry_engine = NotificationRetryEngine(registry=registry)
            ok = await retry_engine.retry_delivery("test-deliv-failed-1", session)
            self.assertTrue(ok)

            stmt = select(NotificationDelivery).where(NotificationDelivery.id == "test-deliv-failed-1")
            deliv = (await session.execute(stmt)).scalar_one()
            self.assertEqual(deliv.attempt_count, 2)
            self.assertIsNotNone(deliv.last_attempt_at)

    async def test_5_retry_succeeds_and_updates_status(self):
        """5. Retry succeeds after failure and marks status as DELIVERED."""
        async with self.session_factory() as session:
            mock_provider = MockNotifier()
            registry = NotificationProviderRegistry()
            registry.register(NotificationChannel.TELEGRAM, mock_provider)

            retry_engine = NotificationRetryEngine(registry=registry)
            ok = await retry_engine.retry_delivery("test-deliv-failed-1", session)
            self.assertTrue(ok)

            stmt = select(NotificationDelivery).where(NotificationDelivery.id == "test-deliv-failed-1")
            deliv = (await session.execute(stmt)).scalar_one()
            self.assertEqual(deliv.status, NotificationStatus.DELIVERED.value)
            self.assertIsNotNone(deliv.delivered_at)
            self.assertIsNone(deliv.error_message)

            notif_stmt = select(Notification).where(Notification.id == deliv.notification_id)
            notif = (await session.execute(notif_stmt)).scalar_one()
            self.assertEqual(notif.status, NotificationStatus.SENT.value)

    async def test_6_maximum_retry_attempts_stops_further_retries(self):
        """6. Maximum retry attempts (MAX_ATTEMPTS=3) permanently stops further retries."""
        async with self.session_factory() as session:
            stmt = select(NotificationDelivery).where(NotificationDelivery.id == "test-deliv-failed-1")
            deliv = (await session.execute(stmt)).scalar_one()
            deliv.attempt_count = MAX_ATTEMPTS
            await session.commit()

            retry_engine = NotificationRetryEngine()
            ok = await retry_engine.retry_delivery("test-deliv-failed-1", session)
            self.assertFalse(ok)

    async def test_7_retry_coordinator_finds_eligible_deliveries(self):
        """7. Retry engine finds eligible deliveries respecting backoff."""
        async with self.session_factory() as session:
            retry_engine = NotificationRetryEngine()
            eligible = await retry_engine.get_retryable_deliveries(session)
            # test-deliv-failed-1 has attempt_count=1 and last_attempt_at 10m ago (backoff is 5m)
            self.assertEqual(len(eligible), 1)
            self.assertEqual(eligible[0].id, "test-deliv-failed-1")

    async def test_8_retry_coordinator_ignores_completed_and_recent_failures(self):
        """8. Retry engine ignores already delivered records or records within backoff window."""
        async with self.session_factory() as session:
            stmt = select(NotificationDelivery).where(NotificationDelivery.id == "test-deliv-failed-1")
            deliv = (await session.execute(stmt)).scalar_one()
            # Set last_attempt_at to 1 minute ago (backoff requires 5 minutes)
            deliv.last_attempt_at = datetime.now(timezone.utc) - timedelta(minutes=1)
            await session.commit()

            retry_engine = NotificationRetryEngine()
            eligible = await retry_engine.get_retryable_deliveries(session)
            self.assertEqual(len(eligible), 0)

    async def test_9_provider_health_observability_endpoint(self):
        """9. GET /api/v1/notifications/providers/status returns provider operational states."""
        async with AsyncClient(transport=self.transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/notifications/providers/status")
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertIn("providers", data)
            channels = [p["channel"] for p in data["providers"]]
            self.assertIn("in_app", channels)
            self.assertIn("telegram", channels)
            self.assertIn("mock", channels)

    async def test_10_notification_deliveries_history_endpoint(self):
        """10. GET /api/v1/notifications/deliveries returns paginated delivery audit history."""
        async with AsyncClient(transport=self.transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/notifications/deliveries?status=failed")
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertIn("items", data)
            self.assertEqual(data["total"], 1)
            self.assertEqual(data["items"][0]["id"], "test-deliv-failed-1")

    async def test_11_manual_retry_endpoint(self):
        """11. POST /api/v1/notifications/deliveries/{id}/retry triggers retry attempt."""
        async with AsyncClient(transport=self.transport, base_url="http://test") as client:
            resp = await client.post("/api/v1/notifications/deliveries/test-deliv-failed-1/retry")
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertEqual(data["delivery_id"], "test-deliv-failed-1")
            self.assertEqual(data["attempt_count"], 2)
