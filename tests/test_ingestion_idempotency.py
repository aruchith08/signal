"""
Unit & Integration Tests for Priority 5: Ingestion Idempotency & Duplicate Safety
Validates:
- Database unique constraints on RawDiscovery (content_hash, canonical_url)
- Database unique constraints on OpportunityEvent (opportunity_id, content_hash)
- Ingestion pipeline idempotency when processing duplicate items
- Lifecycle engine idempotency preventing duplicate Opportunities and Events
- Notification dispatcher idempotency preventing duplicate alerts to the same user
"""
import asyncio
from datetime import datetime, timezone
from pathlib import Path
import sys
import unittest
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError

from apps.api.models.base import Base
from apps.api.models.discovery import RawDiscovery
from apps.api.models.event import OpportunityEvent
from apps.api.models.opportunity import Opportunity
from apps.api.models.notification import Notification
from apps.api.models.user import User
from apps.api.models.preference import UserNotificationPreference
from connectors.base_connector import RawItem
from services.ingestion.pipeline import IngestionPipeline
from services.lifecycle.engine import LifecycleEngine
from services.intelligence.classifier import ContentUnderstanding
from services.notifications.dispatcher import NotificationDispatcher
from services.notifications.decision_engine import NotificationDecision
from shared.constants import EventType, OpportunityCategory, PriorityLevel, DeliveryMode


class TestIngestionIdempotency(unittest.IsolatedAsyncioTestCase):
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

    async def test_raw_discovery_unique_constraint(self):
        """Database enforces uniqueness on (content_hash, canonical_url)."""
        async with self.session_factory() as session:
            d1 = RawDiscovery(
                content_hash="abc123hash",
                canonical_url="https://example.com/opp1",
                original_url="https://example.com/opp1?utm=test",
                raw_title="Test Opportunity",
                raw_content="Content of test opportunity",
                fetched_at=datetime.now(timezone.utc),
                status="discovered",
            )
            session.add(d1)
            await session.commit()

            d2 = RawDiscovery(
                content_hash="abc123hash",
                canonical_url="https://example.com/opp1",
                original_url="https://example.com/opp1?utm=another",
                raw_title="Test Opportunity Duplicate",
                raw_content="Content of test opportunity duplicate",
                fetched_at=datetime.now(timezone.utc),
                status="discovered",
            )
            session.add(d2)
            with self.assertRaises(IntegrityError):
                await session.commit()

    async def test_opportunity_event_unique_constraint(self):
        """Database enforces uniqueness on (opportunity_id, content_hash)."""
        async with self.session_factory() as session:
            opp = Opportunity(
                title="Hackathon 2026",
                canonical_name="Hackathon 2026",
                slug="hackathon-2026",
                category="hackathon",
                current_state="announced",
                content_hash="opphash1",
            )
            session.add(opp)
            await session.commit()

            e1 = OpportunityEvent(
                opportunity_id=opp.id,
                content_hash="eventhash123",
                event_type="announced",
                title="Registration Open",
            )
            session.add(e1)
            await session.commit()

            e2 = OpportunityEvent(
                opportunity_id=opp.id,
                content_hash="eventhash123",
                event_type="announced",
                title="Registration Open Duplicate",
            )
            session.add(e2)
            with self.assertRaises(IntegrityError):
                await session.commit()

    async def test_pipeline_process_raw_item_idempotency(self):
        """Processing the exact same RawItem sequentially creates only one discovery and opportunity."""
        item = RawItem(
            source_name="sih",
            title="Smart India Hackathon 2026: Registration Open",
            content="Smart India Hackathon 2026 registration is open for students and developers. Submit project proposals before deadline. Hackathon contest with cash prizes.",
            url="https://sih.gov.in/sih2026",
            published_at=datetime.now(timezone.utc),
            source_identifier="sih-2026",
        )

        async with self.session_factory() as session:
            pipeline = IngestionPipeline(session)
            opp1 = await pipeline.process_raw_item(item)
            await session.commit()
            self.assertIsNotNone(opp1)

            # Process identical item again
            opp2 = await pipeline.process_raw_item(item)
            await session.commit()
            self.assertIsNotNone(opp2)
            self.assertEqual(opp1.id, opp2.id)

            # Verify total discoveries and opportunities in db
            disc_count = (await session.execute(select(func.count(RawDiscovery.id)))).scalar()
            opp_count = (await session.execute(select(func.count(Opportunity.id)))).scalar()
            event_count = (await session.execute(select(func.count(OpportunityEvent.id)))).scalar()

            self.assertEqual(disc_count, 1)
            self.assertEqual(opp_count, 1)
            self.assertEqual(event_count, 1)

    async def test_notification_dispatcher_duplicate_prevention(self):
        """Dispatcher prevents duplicate notifications for the same user and event."""
        async with self.session_factory() as session:
            user = User(email="dev@example.com", username="dev_user", is_active=True)
            session.add(user)

            opp = Opportunity(
                title="Smart India Hackathon 2026",
                canonical_name="Smart India Hackathon 2026",
                slug="sih-2026",
                category="hackathon",
                current_state="announced",
                content_hash="sihhash",
            )
            session.add(opp)
            await session.flush()

            event = OpportunityEvent(
                opportunity_id=opp.id,
                content_hash="siheventhash",
                event_type="announced",
                title="SIH 2026 Announced",
            )
            session.add(event)
            await session.commit()

            decision = NotificationDecision(
                should_notify=True,
                delivery_mode=DeliveryMode.INSTANT,
                priority=PriorityLevel.HIGH,
                reason="High user relevance",
            )

            dispatcher = NotificationDispatcher(session)

            # First dispatch succeeds
            notif1 = await dispatcher.dispatch(user, opp, decision, event)
            await session.commit()
            self.assertIsNotNone(notif1)

            # Second dispatch for the same user and event is idempotently skipped
            notif2 = await dispatcher.dispatch(user, opp, decision, event)
            await session.commit()
            self.assertIsNotNone(notif2)
            self.assertEqual(notif1.id, notif2.id)

            # Only 1 Notification row exists in DB
            notif_count = (
                await session.execute(
                    select(func.count(Notification.id)).where(Notification.user_id == user.id)
                )
            ).scalar()
            self.assertEqual(notif_count, 1)
