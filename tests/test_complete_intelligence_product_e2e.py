"""
SIGNAL 📡 — Complete Intelligence Product End-to-End Test Suite
Validates the entire chain from Source -> Ingestion -> Classification -> Entity Resolution
-> Verification -> Personalization -> Notification Decision -> Multi-Channel Delivery -> Digest.
"""
from datetime import datetime, timezone, timedelta
import unittest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select

from apps.api.main import app
from apps.api.database import get_db, Base
from apps.api.models.user import User, UserProfile, UserInterest
from apps.api.models.preference import UserNotificationPreference
from apps.api.models.source import Source
from apps.api.models.opportunity import Opportunity
from apps.api.models.event import OpportunityEvent
from apps.api.models.discovery import RawDiscovery
from apps.api.models.notification import Notification

from connectors.base_connector import RawItem
from services.ingestion.pipeline import IngestionPipeline
from services.intelligence.classifier import Classifier
from services.lifecycle.engine import LifecycleEngine
from services.personalization.relevance_engine import PersonalizationEngine
from services.notifications.decision_engine import NotificationDecisionEngine
from services.notifications.dispatcher import NotificationDispatcher
from services.notifications.digest import DigestEngine, DigestType
from services.intelligence.router import ai_router

from shared.constants import (
    OpportunityCategory,
    OpportunityStatus,
    EventType,
    NotificationChannel,
    EligibilityStatus,
    ChangeType,
)


class TestCompleteIntelligenceProductE2E(unittest.IsolatedAsyncioTestCase):

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

    async def test_end_to_end_discovery_to_notification(self):
        """Full pipeline: Raw Item -> Discovery -> Classification -> Opportunity -> Verification -> Personalization -> Notification."""
        async with self.session_factory() as session:
            # 1. Setup Student User
            user = User(
                email="rachel.green@student.signal.dev",
                username="rachel_g",
                full_name="Rachel Green",
                is_active=True,
            )
            session.add(user)
            await session.flush()

            profile = UserProfile(
                user_id=user.id,
                education_level="Undergraduate",
                country="India",
                branch="Computer Science",
                current_year=3,
                career_interests="Artificial Intelligence, Machine Learning",
                preferred_opportunity_types="hackathon, ai_ml, competition",
            )
            pref = UserNotificationPreference(
                user_id=user.id,
                enabled=True,
                min_relevance_score=50,
                instant_alerts_enabled=True,
                digest_enabled=True,
            )
            interest = UserInterest(
                user_id=user.id,
                category="ai_ml",
                tag="machine_learning",
                weight=1.0,
            )
            session.add_all([profile, pref, interest])

            # 2. Setup Source
            src = Source(
                name="Kaggle",
                slug="kaggle",
                category="ai_ml",
                source_type="api",
                base_url="https://www.kaggle.com",
            )
            session.add(src)
            await session.commit()
            user_id = user.id
            source_id = src.id

        # 3. Simulate Ingestion of Raw Item
        deadline_dt = datetime.now(timezone.utc) + timedelta(days=14)
        raw_item = RawItem(
            title="Global AI Grand Prix 2026",
            url="https://www.kaggle.com/c/ai-grand-prix-2026",
            content="Official Global AI Grand Prix 2026 Machine Learning Competition with $50,000 in prizes.",
            source_name="Kaggle",
            source_identifier="ai-gp-2026",
            published_at=datetime.now(timezone.utc),
            metadata={
                "organization": "Kaggle",
                "category": OpportunityCategory.AI_ML.value,
                "deadline_date": deadline_dt.isoformat(),
                "prize": "$50,000",
                "eligibility": "Students, Engineers, Global Data Scientists",
            },
        )

        async with self.session_factory() as session:
            # Step A: Ingestion Pipeline
            pipeline = IngestionPipeline(session)
            discovery = await pipeline.ingest_raw_item(raw_item, source_id=source_id)
            self.assertIsNotNone(discovery)
            await session.commit()

            # Step B: Classification (Deterministic-first)
            understanding = await Classifier.classify_with_fallback(
                raw_title=discovery.raw_title,
                raw_content=discovery.raw_content,
                connector_metadata=discovery.metadata_json,
                source_category="ai_ml",
                source_name="Kaggle",
            )
            self.assertEqual(understanding.category, OpportunityCategory.AI_ML)
            self.assertTrue(understanding.is_actionable_opportunity)

            # Step C: Lifecycle & Entity Resolution
            lifecycle_engine = LifecycleEngine(session)
            opp = await lifecycle_engine.process_discovery_lifecycle(
                discovery=discovery,
                understanding=understanding,
                source_id=source_id,
                source_category="ai_ml",
                source_trust="high",
            )
            self.assertIsNotNone(opp)
            self.assertEqual(opp.title, "Global AI Grand Prix 2026")
            await session.commit()
            opp_id = opp.id

        # Step D: Personalization & Relevance Evaluation
        async with self.session_factory() as session:
            user_obj = (await session.execute(select(User).where(User.id == user_id))).scalars().first()
            opp_obj = (await session.execute(select(Opportunity).where(Opportunity.id == opp_id))).scalars().first()

            relevance_engine = PersonalizationEngine(session)
            relevance_res = await relevance_engine.evaluate_relevance(user_obj, opp_obj)
            self.assertGreaterEqual(relevance_res.score, 50)
            self.assertIn("machine_learning", relevance_res.matched_interests)
            self.assertTrue(len(relevance_res.reasons) > 0)

            # Step E: Automated Notification Delivery Verification
            notifs = (await session.execute(select(Notification).where(Notification.user_id == user_id))).scalars().all()
            self.assertEqual(len(notifs), 1)
            self.assertEqual(notifs[0].user_id, user_id)
            self.assertIn("Global AI Grand Prix", notifs[0].message)

            # Step F: Verify Anti-Fatigue Deduplication prevents duplicate delivery
            decision_engine = NotificationDecisionEngine(session)
            repeat_decision = await decision_engine.evaluate_notification_decision(user_obj, opp_obj)
            self.assertFalse(repeat_decision.should_notify)
            self.assertIn("already delivered", repeat_decision.reason)

    async def test_duplicate_item_idempotency(self):
        """Verify re-ingesting the identical raw item does not create duplicate opportunities or events."""
        async with self.session_factory() as session:
            src = Source(name="Unstop", slug="unstop", category="hackathon", source_type="api", base_url="https://unstop.com")
            session.add(src)
            await session.commit()
            source_id = src.id

        raw_item = RawItem(
            title="National Code Sprint 2026",
            url="https://unstop.com/hackathons/national-code-sprint-2026",
            content="Hackathon coding sprint with industry mentors.",
            source_name="Unstop",
            source_identifier="ncs-2026",
            published_at=datetime.now(timezone.utc),
            metadata={"organization": "Unstop", "category": "hackathon"},
        )

        async with self.session_factory() as session:
            pipeline = IngestionPipeline(session)
            disc1 = await pipeline.ingest_raw_item(raw_item, source_id=source_id)
            await session.commit()

            understanding = Classifier.classify(disc1.raw_title, disc1.raw_content, connector_metadata=disc1.metadata_json)
            lifecycle = LifecycleEngine(session)
            opp1 = await lifecycle.process_discovery_lifecycle(disc1, understanding, source_id=source_id)
            await session.commit()
            opp_id = opp1.id

        # Ingest identical item a second time
        async with self.session_factory() as session:
            pipeline = IngestionPipeline(session)
            disc2 = await pipeline.ingest_raw_item(raw_item, source_id=source_id)
            await session.commit()
            self.assertEqual(disc1.id, disc2.id)  # Idempotent discovery reuse

            understanding2 = Classifier.classify(disc2.raw_title, disc2.raw_content, connector_metadata=disc2.metadata_json)
            lifecycle2 = LifecycleEngine(session)
            opp2 = await lifecycle2.process_discovery_lifecycle(disc2, understanding2, source_id=source_id)
            await session.commit()

            # Confirm opportunity count remains exactly 1
            opp_count = (await session.execute(select(Opportunity))).scalars().all()
            self.assertEqual(len(opp_count), 1)

    async def test_deadline_change_detection_and_events(self):
        """Verify updating an opportunity's deadline detects ChangeSet and emits DEADLINE_CHANGED event."""
        async with self.session_factory() as session:
            src = Source(name="SIH", slug="sih", category="hackathon", source_type="official_website", base_url="https://sih.gov.in")
            session.add(src)
            await session.commit()
            source_id = src.id

        d1 = datetime.now(timezone.utc) + timedelta(days=10)
        item1 = RawItem(
            title="Smart India Hackathon 2026 Season 8",
            url="https://sih.gov.in/challenge-101",
            content="SIH 2026 official nationwide hackathon.",
            source_name="SIH",
            source_identifier="sih-2026-101",
            metadata={"organization": "AICTE", "category": "hackathon", "deadline_date": d1.isoformat()},
        )

        async with self.session_factory() as session:
            pipeline = IngestionPipeline(session)
            disc1 = await pipeline.ingest_raw_item(item1, source_id=source_id)
            await session.commit()

            understanding1 = Classifier.classify(disc1.raw_title, disc1.raw_content, connector_metadata=disc1.metadata_json)
            lifecycle = LifecycleEngine(session)
            opp = await lifecycle.process_discovery_lifecycle(disc1, understanding1, source_id=source_id)
            await session.commit()
            opp_id = opp.id

        # Item with extended deadline
        d2 = datetime.now(timezone.utc) + timedelta(days=20)
        item2 = RawItem(
            title="Smart India Hackathon 2026 Season 8",
            url="https://sih.gov.in/challenge-101",
            content="SIH 2026 deadline extended by 10 days!",
            source_name="SIH",
            source_identifier="sih-2026-101",
            metadata={"organization": "AICTE", "category": "hackathon", "deadline_date": d2.isoformat()},
        )

        async with self.session_factory() as session:
            pipeline = IngestionPipeline(session)
            disc2 = await pipeline.ingest_raw_item(item2, source_id=source_id)
            await session.commit()

            understanding2 = Classifier.classify(disc2.raw_title, disc2.raw_content, connector_metadata=disc2.metadata_json)
            lifecycle = LifecycleEngine(session)
            updated_opp = await lifecycle.process_discovery_lifecycle(disc2, understanding2, source_id=source_id)
            await session.commit()

            # Verify that DEADLINE_CHANGED event was created
            events = (
                await session.execute(
                    select(OpportunityEvent)
                    .where(OpportunityEvent.opportunity_id == opp_id)
                    .order_by(OpportunityEvent.created_at.desc())
                )
            ).scalars().all()

            deadline_events = [e for e in events if e.event_type == EventType.DEADLINE_CHANGED.value]
            self.assertGreaterEqual(len(deadline_events), 1)
            self.assertIn("Deadline Changed", deadline_events[0].title)

    async def test_digest_engine_generation(self):
        """Verify DigestEngine compiles and formats Daily and Urgent digests."""
        async with self.session_factory() as session:
            user = User(email="digest.tester@signal.dev", username="digest_user", is_active=True)
            session.add(user)
            await session.flush()
            pref = UserNotificationPreference(user_id=user.id, enabled=True, min_relevance_score=30, digest_enabled=True)
            interest = UserInterest(user_id=user.id, category="hackathon", tag="web3", weight=1.0)
            session.add_all([pref, interest])

            opp = Opportunity(
                title="Urgent Web3 Hackathon",
                slug="urgent-web3-hackathon",
                category="hackathon",
                confidence_score=90,
                status=OpportunityStatus.OPEN.value,
            )
            session.add(opp)
            await session.flush()
            event = OpportunityEvent(
                opportunity_id=opp.id,
                title="Registration Open",
                event_type=EventType.REGISTRATION_OPEN.value,
                deadline_date=datetime.now(timezone.utc) + timedelta(hours=24),
            )
            session.add(event)
            await session.commit()

            digest_engine = DigestEngine(session)
            payload = await digest_engine.generate_user_digest(user, digest_type=DigestType.URGENT_48H)
            self.assertIsNotNone(payload)
            self.assertEqual(payload.digest_type, DigestType.URGENT_48H)
            self.assertIn("Urgent Web3 Hackathon", payload.body)

            success = await digest_engine.dispatch_digest(payload)
            await session.commit()
            self.assertTrue(success)

    async def test_operator_diagnostics_endpoint(self):
        """Verify /api/v1/dashboard/diagnostics consolidates operational metrics."""
        async with AsyncClient(transport=self.transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/dashboard/diagnostics")
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertIn("sources", data)
            self.assertIn("verification", data)
            self.assertIn("notifications", data)
            self.assertIn("scheduler_running", data)
