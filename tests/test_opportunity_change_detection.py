"""
Unit and Integration Tests for Phase 5A: Opportunity Structured Change Detection
Validates:
- Unchanged data produces 0 ChangeSets
- Deadline change creates 1 ChangeSet (field_name='deadline_date', change_type='deadline_changed', CRITICAL)
- State / status changes create appropriate ChangeSets
- Multiple field modifications generate multiple ChangeSets
- Repeated ingestion of identical data creates 0 duplicate ChangeSets
- Brand-new opportunity creation generates 0 ChangeSets
- Full integration with LifecycleEngine update flow
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
from apps.api.models.discovery import RawDiscovery
from services.ingestion.opportunity_change_detection import OpportunityChangeDetector
from services.intelligence.classifier import ContentUnderstanding
from services.lifecycle.engine import LifecycleEngine
from shared.constants import (
    ChangeType,
    ContentClassification,
    EventType,
    OpportunityCategory,
    OpportunityStatus,
    PriorityLevel,
    VerificationStatus,
)
from shared.utils import compute_content_hash


class TestOpportunityChangeDetection(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        self.session_factory = async_sessionmaker(
            bind=self.engine, class_=AsyncSession, expire_on_commit=False
        )

        async with self.session_factory() as session:
            opp = Opportunity(
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
                eligibility="University students worldwide",
                application_url="https://summerofcode.withgoogle.com",
                raw_content="GSoC 2026 announced.",
                summary="GSoC 2026 announced.",
                content_hash=compute_content_hash("gsoc-2026-initial"),
            )
            session.add(opp)
            await session.commit()
            self.opp_id = opp.id

    async def asyncTearDown(self):
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await self.engine.dispose()

    async def test_1_unchanged_data_produces_zero_changesets(self):
        """Re-ingesting identical values must result in 0 ChangeSet records."""
        async with self.session_factory() as session:
            opp = await session.get(Opportunity, self.opp_id)
            detector = OpportunityChangeDetector()

            incoming = {
                "title": "Google Summer of Code 2026",
                "current_state": EventType.ANNOUNCED.value,
                "season": "2026",
                "year": 2026,
                "eligibility": "University students worldwide",
                "application_url": "https://summerofcode.withgoogle.com",
            }

            changes = await detector.detect_and_record(
                session=session,
                existing_opp=opp,
                incoming_data=incoming,
            )
            await session.commit()

            self.assertEqual(len(changes), 0)
            stmt = select(ChangeSet).where(ChangeSet.opportunity_id == self.opp_id)
            total = (await session.execute(stmt)).scalars().all()
            self.assertEqual(len(total), 0)

    async def test_2_deadline_change_creates_single_critical_changeset(self):
        """Updating deadline_date must produce a ChangeSet with DEADLINE_CHANGED and CRITICAL priority."""
        async with self.session_factory() as session:
            opp = await session.get(Opportunity, self.opp_id)
            detector = OpportunityChangeDetector()

            incoming = {
                "deadline_date": "2026-04-15",
            }

            changes = await detector.detect_and_record(
                session=session,
                existing_opp=opp,
                incoming_data=incoming,
            )
            await session.commit()

            self.assertEqual(len(changes), 1)
            cs = changes[0]
            self.assertEqual(cs.field_name, "deadline_date")
            self.assertIsNone(cs.previous_value)
            self.assertEqual(cs.new_value, "2026-04-15")
            self.assertEqual(cs.change_type, ChangeType.DEADLINE_CHANGED.value)
            self.assertEqual(cs.importance, PriorityLevel.CRITICAL.value)

            # Further update to an existing deadline
            incoming_update = {"deadline_date": "2026-04-20"}
            changes_2 = await detector.detect_and_record(
                session=session,
                existing_opp=opp,
                incoming_data=incoming_update,
            )
            await session.commit()

            self.assertEqual(len(changes_2), 1)
            cs2 = changes_2[0]
            self.assertEqual(cs2.field_name, "deadline_date")
            self.assertEqual(cs2.previous_value, "2026-04-15")
            self.assertEqual(cs2.new_value, "2026-04-20")

    async def test_3_status_and_state_changes(self):
        """Lifecycle state transitions must trigger STATUS_CHANGED or DEADLINE_CHANGED."""
        async with self.session_factory() as session:
            opp = await session.get(Opportunity, self.opp_id)
            detector = OpportunityChangeDetector()

            # Transition from 'announced' to 'registration_open'
            incoming = {"current_state": EventType.REGISTRATION_OPEN.value}
            changes = await detector.detect_and_record(
                session=session,
                existing_opp=opp,
                incoming_data=incoming,
            )
            await session.commit()

            self.assertEqual(len(changes), 1)
            self.assertEqual(changes[0].field_name, "current_state")
            self.assertEqual(changes[0].previous_value, EventType.ANNOUNCED.value)
            self.assertEqual(changes[0].new_value, EventType.REGISTRATION_OPEN.value)
            self.assertEqual(changes[0].change_type, ChangeType.STATUS_CHANGED.value)
            self.assertEqual(changes[0].importance, PriorityLevel.HIGH.value)

            # Transition to a critical deadline event
            opp.current_state = EventType.REGISTRATION_OPEN.value
            incoming_critical = {"current_state": EventType.REGISTRATION_CLOSING.value}
            changes_crit = await detector.detect_and_record(
                session=session,
                existing_opp=opp,
                incoming_data=incoming_critical,
            )
            await session.commit()

            self.assertEqual(len(changes_crit), 1)
            self.assertEqual(changes_crit[0].change_type, ChangeType.DEADLINE_CHANGED.value)
            self.assertEqual(changes_crit[0].importance, PriorityLevel.CRITICAL.value)

    async def test_4_multiple_field_changes(self):
        """Changing multiple monitored fields must create a ChangeSet for each modified field."""
        async with self.session_factory() as session:
            opp = await session.get(Opportunity, self.opp_id)
            detector = OpportunityChangeDetector()

            incoming = {
                "title": "Google Summer of Code 2026 - Extended Edition",
                "application_url": "https://summerofcode.withgoogle.com/apply-now",
                "eligibility": "Open to all students & open source contributors",
                "year": 2027,
                "deadline_date": "2026-05-01",
            }

            changes = await detector.detect_and_record(
                session=session,
                existing_opp=opp,
                incoming_data=incoming,
            )
            await session.commit()

            self.assertEqual(len(changes), 5)
            field_names = {c.field_name for c in changes}
            self.assertEqual(
                field_names,
                {"title", "application_url", "eligibility", "year", "deadline_date"},
            )

    async def test_5_repeated_ingestion_prevents_duplicate_changesets(self):
        """Submitting the exact same changed data twice must NOT insert duplicate ChangeSets."""
        async with self.session_factory() as session:
            opp = await session.get(Opportunity, self.opp_id)
            detector = OpportunityChangeDetector()

            incoming = {
                "title": "Google Summer of Code 2026 - Updated Title",
                "deadline_date": "2026-04-10",
            }

            # First run: 2 ChangeSets created
            first_run = await detector.detect_and_record(
                session=session,
                existing_opp=opp,
                incoming_data=incoming,
            )
            await session.commit()
            self.assertEqual(len(first_run), 2)

            # Second run with same data: must create 0 ChangeSets
            second_run = await detector.detect_and_record(
                session=session,
                existing_opp=opp,
                incoming_data=incoming,
            )
            await session.commit()
            self.assertEqual(len(second_run), 0)

            # Check database row count
            stmt = select(ChangeSet).where(ChangeSet.opportunity_id == self.opp_id)
            total = (await session.execute(stmt)).scalars().all()
            self.assertEqual(len(total), 2)

    async def test_6_new_opportunity_creation_yields_zero_changesets(self):
        """Initial creation of an Opportunity must NOT generate ChangeSets."""
        async with self.session_factory() as session:
            detector = OpportunityChangeDetector()

            incoming = {
                "title": "Brand New Hackathon 2026",
                "current_state": EventType.ANNOUNCED.value,
                "season": "1",
                "year": 2026,
                "deadline_date": "2026-10-01",
                "application_url": "https://hackathon.example.com",
            }

            # existing_opp is None for brand new entity
            changes = await detector.detect_and_record(
                session=session,
                existing_opp=None,
                incoming_data=incoming,
            )
            self.assertEqual(len(changes), 0)

    async def test_7_lifecycle_engine_integration(self):
        """Processing an update to an existing matched opportunity via LifecycleEngine records ChangeSets."""
        async with self.session_factory() as session:
            engine = LifecycleEngine(session)

            # Match the existing opportunity via canonical url
            raw_discovery = RawDiscovery(
                canonical_url="https://summerofcode.withgoogle.com",
                original_url="https://summerofcode.withgoogle.com",
                raw_title="Google Summer of Code 2026 - Registrations Open",
                raw_content="Registrations are now open for Google Summer of Code 2026.",
                content_hash=compute_content_hash("gsoc-discovery-update-test"),
            )
            session.add(raw_discovery)
            await session.flush()

            understanding = ContentUnderstanding(
                opportunity_name="Google Summer of Code 2026",
                canonical_name="Google Summer of Code 2026",
                classification=ContentClassification.OPPORTUNITY,
                lifecycle_event_type=EventType.REGISTRATION_OPEN,
                deadline_date=datetime(2026, 4, 30, tzinfo=timezone.utc),
                is_actionable_opportunity=True,
                season="2026",
                year=2026,
            )

            result_opp = await engine.process_discovery_lifecycle(
                discovery=raw_discovery,
                understanding=understanding,
                source_trust="high",
            )
            await session.commit()

            self.assertIsNotNone(result_opp)
            self.assertEqual(result_opp.id, self.opp_id)
            self.assertEqual(result_opp.current_state, EventType.REGISTRATION_OPEN.value)

            # Check that ChangeSets were recorded in the lifecycle run
            stmt = select(ChangeSet).where(ChangeSet.opportunity_id == self.opp_id)
            changes = (await session.execute(stmt)).scalars().all()
            self.assertGreaterEqual(len(changes), 1)

            changed_fields = {c.field_name for c in changes}
            self.assertIn("current_state", changed_fields)


if __name__ == "__main__":
    unittest.main()
