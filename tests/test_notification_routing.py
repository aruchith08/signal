"""
Unit and Integration Tests for Phase 5B: Notification Intelligence & Delivery Pipeline
Validates:
- InAppNotifier functionality and health check
- NotificationDispatcher persists both Notification and NotificationDelivery records
- NotificationDispatcher failure logs error_message and FAILED status in NotificationDelivery
- ChangeSetNotificationRouter routes alerts to direct subscribers (saved/followed)
- ChangeSetNotificationRouter respects anti-fatigue & deduplication limits
- End-to-end integration: LifecycleEngine triggers ChangeSet detection and Notification routing
"""
from datetime import datetime, timezone
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select

from apps.api.models.base import Base
from apps.api.models import Opportunity, ChangeSet, Source
from apps.api.models.user import User, UserProfile, UserInterest
from apps.api.models.preference import UserNotificationPreference
from apps.api.models.interaction import UserOpportunityInteraction
from apps.api.models.notification import Notification
from apps.api.models.notification_delivery import NotificationDelivery
from apps.api.models.discovery import RawDiscovery
from services.notifications.base_notifier import BaseNotifier
from services.notifications.in_app_notifier import InAppNotifier
from services.notifications.mock_notifier import MockNotifier
from services.notifications.dispatcher import NotificationDispatcher
from services.notifications.decision_engine import NotificationDecision
from services.notifications.change_set_router import ChangeSetNotificationRouter
from services.intelligence.classifier import ContentUnderstanding
from services.lifecycle.engine import LifecycleEngine
from shared.constants import (
    ChangeType,
    ContentClassification,
    DeliveryMode,
    EventType,
    NotificationChannel,
    NotificationStatus,
    OpportunityCategory,
    OpportunityStatus,
    PriorityLevel,
    VerificationStatus,
)
from shared.utils import compute_content_hash


class FailingNotifier(BaseNotifier):
    """Failing provider to test error logging in NotificationDelivery."""
    def __init__(self):
        super().__init__(channel=NotificationChannel.TELEGRAM)

    async def send(self, recipient, message, priority=PriorityLevel.MEDIUM, metadata=None):
        raise ConnectionError("Telegram API timeout")

    async def health_check(self):
        return {"status": "unhealthy", "error": "timeout"}


class TestNotificationPipeline(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        self.session_factory = async_sessionmaker(
            bind=self.engine, class_=AsyncSession, expire_on_commit=False
        )

        async with self.session_factory() as session:
            # 1. Base Opportunity
            opp = Opportunity(
                id="opp-test-1",
                title="Google Summer of Code 2026",
                canonical_name="Google Summer of Code 2026",
                slug="gsoc-2026",
                category=OpportunityCategory.OPEN_SOURCE_PROGRAM.value,
                status=OpportunityStatus.ACTIVE.value,
                current_state=EventType.ANNOUNCED.value,
                verification_status=VerificationStatus.VERIFIED.value,
                confidence_score=95,
                official=True,
                season="2026",
                year=2026,
                application_url="https://summerofcode.withgoogle.com",
            )
            session.add(opp)

            # 2. User 1: Subscribed / Followed User with In-App Preference
            user1 = User(
                id="user-sub-1",
                username="dev_sub_1",
                email="dev1@example.com",
                full_name="Dev Subscriber",
                is_active=True,
            )
            session.add(user1)
            pref1 = UserNotificationPreference(
                user_id=user1.id,
                enabled=True,
                min_relevance_score=60,
                instant_alerts_enabled=True,
                telegram_chat_id="chat_dev1",
            )
            session.add(pref1)
            interaction1 = UserOpportunityInteraction(
                user_id=user1.id,
                opportunity_id=opp.id,
                is_saved=True,
                is_followed=True,
            )
            session.add(interaction1)

            # 3. User 2: Inactive User (Should be skipped by anti-fatigue)
            user2 = User(
                id="user-inactive-2",
                username="inactive_user_2",
                email="inactive@example.com",
                full_name="Inactive User",
                is_active=False,
            )
            session.add(user2)

            await session.commit()

    async def asyncTearDown(self):
        await self.engine.dispose()

    async def test_in_app_notifier_health_and_send(self):
        """Verify InAppNotifier provider methods."""
        notifier = InAppNotifier()
        health = await notifier.health_check()
        self.assertEqual(health["status"], "healthy")
        self.assertEqual(health["channel"], "in_app")

        sent = await notifier.send(recipient="user-123", message="Test alert")
        self.assertTrue(sent)

    async def test_dispatcher_creates_notification_and_delivery(self):
        """Verify NotificationDispatcher creates both Notification and NotificationDelivery rows."""
        async with self.session_factory() as session:
            mock_provider = MockNotifier()
            dispatcher = NotificationDispatcher(session, provider=mock_provider)

            opp_stmt = select(Opportunity).where(Opportunity.id == "opp-test-1")
            opp = (await session.execute(opp_stmt)).scalar_one()

            user_stmt = select(User).where(User.id == "user-sub-1")
            user = (await session.execute(user_stmt)).scalar_one()

            decision = NotificationDecision(
                should_notify=True,
                delivery_mode=DeliveryMode.INSTANT,
                priority=PriorityLevel.HIGH,
                reason="Direct test notification",
            )

            notif = await dispatcher.dispatch(user=user, opportunity=opp, decision=decision)
            self.assertIsNotNone(notif)
            self.assertEqual(notif.status, NotificationStatus.SENT.value)

            # Query deliveries
            deliv_stmt = select(NotificationDelivery).where(NotificationDelivery.notification_id == notif.id)
            deliveries = (await session.execute(deliv_stmt)).scalars().all()
            self.assertEqual(len(deliveries), 1)
            delivery = deliveries[0]
            self.assertEqual(delivery.status, NotificationStatus.DELIVERED.value)
            self.assertEqual(delivery.attempt_count, 1)
            self.assertIsNotNone(delivery.delivered_at)
            self.assertIsNone(delivery.error_message)

    async def test_dispatcher_failure_logs_error_in_delivery(self):
        """Verify failing provider logs FAILED status and error_message in NotificationDelivery."""
        async with self.session_factory() as session:
            failing_provider = FailingNotifier()
            dispatcher = NotificationDispatcher(session, provider=failing_provider)

            opp_stmt = select(Opportunity).where(Opportunity.id == "opp-test-1")
            opp = (await session.execute(opp_stmt)).scalar_one()

            user_stmt = select(User).where(User.id == "user-sub-1")
            user = (await session.execute(user_stmt)).scalar_one()

            decision = NotificationDecision(
                should_notify=True,
                delivery_mode=DeliveryMode.INSTANT,
                priority=PriorityLevel.CRITICAL,
                reason="Failure test",
            )

            notif = await dispatcher.dispatch(user=user, opportunity=opp, decision=decision)
            self.assertIsNotNone(notif)
            self.assertEqual(notif.status, NotificationStatus.FAILED.value)
            self.assertIn("timeout", notif.error_message.lower())

            deliv_stmt = select(NotificationDelivery).where(NotificationDelivery.notification_id == notif.id)
            deliveries = (await session.execute(deliv_stmt)).scalars().all()
            self.assertEqual(len(deliveries), 1)
            delivery = deliveries[0]
            self.assertEqual(delivery.status, NotificationStatus.FAILED.value)
            self.assertEqual(delivery.attempt_count, 1)
            self.assertIn("timeout", delivery.error_message.lower())

    async def test_change_set_router_dispatches_to_subscribers(self):
        """Verify ChangeSetNotificationRouter routes notifications to interested subscribers."""
        async with self.session_factory() as session:
            mock_provider = MockNotifier()
            router = ChangeSetNotificationRouter(provider=mock_provider)

            opp_stmt = select(Opportunity).where(Opportunity.id == "opp-test-1")
            opp = (await session.execute(opp_stmt)).scalar_one()

            cs = ChangeSet(
                opportunity_id=opp.id,
                field_name="deadline_date",
                previous_value="2026-04-01T23:59:59Z",
                new_value="2026-04-15T23:59:59Z",
                change_type=ChangeType.DEADLINE_CHANGED.value,
                importance=PriorityLevel.CRITICAL.value,
                detected_at=datetime.now(timezone.utc),
            )
            session.add(cs)
            await session.flush()

            notifications = await router.route_opportunity_activity(
                session=session,
                opportunity=opp,
                change_sets=[cs],
            )
            self.assertTrue(len(notifications) >= 1)
            notif = notifications[0]
            self.assertEqual(notif.user_id, "user-sub-1")
            self.assertEqual(notif.opportunity_id, opp.id)

            # Deduplication: Re-running router on same opportunity activity produces 0 new notifications
            duplicate_run = await router.route_opportunity_activity(
                session=session,
                opportunity=opp,
                change_sets=[cs],
            )
            self.assertEqual(len(duplicate_run), 0)

    async def test_lifecycle_engine_end_to_end_routing(self):
        """Verify LifecycleEngine detects changes and automatically dispatches notifications."""
        async with self.session_factory() as session:
            mock_provider = MockNotifier()
            router = ChangeSetNotificationRouter(provider=mock_provider)
            engine = LifecycleEngine(session, notification_router=router)

            source = Source(
                name="Google Open Source Blog",
                slug="google-blog",
                base_url="https://opensource.googleblog.com",
                trust_level="high",
            )
            session.add(source)
            await session.flush()

            discovery = RawDiscovery(
                source_id=source.id,
                original_url="https://summerofcode.withgoogle.com",
                canonical_url="https://summerofcode.withgoogle.com",
                raw_title="Google Summer of Code 2026 Deadline Extended",
                raw_content="The deadline for GSoC 2026 has been extended to April 15, 2026.",
                content_hash=compute_content_hash("gsoc-extended-announcement"),
            )
            session.add(discovery)
            await session.flush()

            understanding = ContentUnderstanding(
                is_opportunity=True,
                is_actionable_opportunity=True,
                classification=ContentClassification.OPPORTUNITY,
                opportunity_name="Google Summer of Code 2026",
                canonical_name="Google Summer of Code 2026",
                category=OpportunityCategory.OPEN_SOURCE_PROGRAM,
                lifecycle_event_type=EventType.DEADLINE_EXTENDED,
                event_title="GSoC 2026 Deadline Extended",
                season="2026",
                year=2026,
                deadline_date=datetime(2026, 4, 15, 23, 59, 59, tzinfo=timezone.utc),
                confidence=0.98,
            )

            updated_opp = await engine.process_discovery_lifecycle(
                discovery=discovery,
                understanding=understanding,
                source_id=source.id,
                source_trust=source.trust_level,
                source_category="open_source",
            )
            self.assertEqual(updated_opp.id, "opp-test-1")

            # Check that ChangeSet was created
            cs_stmt = select(ChangeSet).where(ChangeSet.opportunity_id == updated_opp.id)
            changesets = (await session.execute(cs_stmt)).scalars().all()
            self.assertTrue(len(changesets) >= 1)

            # Check that Notification was routed and delivered
            notif_stmt = select(Notification).where(
                Notification.opportunity_id == updated_opp.id,
                Notification.user_id == "user-sub-1",
            )
            notifications = (await session.execute(notif_stmt)).scalars().all()
            self.assertTrue(len(notifications) >= 1)

            # Check that NotificationDelivery was recorded
            deliv_stmt = select(NotificationDelivery).where(
                NotificationDelivery.notification_id == notifications[0].id
            )
            deliveries = (await session.execute(deliv_stmt)).scalars().all()
            self.assertTrue(len(deliveries) >= 1)
            self.assertEqual(deliveries[0].status, NotificationStatus.DELIVERED.value)
