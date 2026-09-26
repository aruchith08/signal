"""
Test Observability, Health Probes, and Verification Resolution Endpoints
"""
import unittest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from apps.api.main import app
from apps.api.database import get_db, Base
from apps.api.models.opportunity import Opportunity
from apps.api.models.verification import VerificationConflict, VerificationReview
from shared.constants import ReviewPriority, ReviewStatus, ConflictStatus


class TestObservabilityAndProbes(unittest.IsolatedAsyncioTestCase):

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

    async def test_health_and_probes(self):
        """Verify /health, /health/live, and /health/ready probes."""
        async with AsyncClient(transport=self.transport, base_url="http://test") as client:
            # 1. Main health
            resp = await client.get("/api/v1/health")
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertIn(data["status"], ("healthy", "degraded"))
            self.assertIn("database", data)
            self.assertIn("ai_gateway", data)

            # 2. Liveness probe
            live_resp = await client.get("/api/v1/health/live")
            self.assertEqual(live_resp.status_code, 200)
            self.assertEqual(live_resp.json()["status"], "alive")

            # 3. Readiness probe
            ready_resp = await client.get("/api/v1/health/ready")
            self.assertEqual(ready_resp.status_code, 200)
            self.assertEqual(ready_resp.json()["status"], "ready")
            self.assertEqual(ready_resp.json()["database"], "connected")

    async def test_audit_logs_alias(self):
        """Verify /audit-logs endpoint returns activity telemetry."""
        async with AsyncClient(transport=self.transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/audit-logs?limit=10")
            self.assertEqual(resp.status_code, 200)
            items = resp.json()
            self.assertIsInstance(items, list)

    async def test_verification_queue_and_resolution(self):
        """Verify /verification/queue alias, approve action, and conflict resolution."""
        async with self.session_factory() as session:
            opp = Opportunity(
                title="Probe Test Hackathon",
                slug="probe-test-hackathon",
                category="hackathon",
                confidence_score=0.9,
            )
            session.add(opp)
            await session.flush()

            review = VerificationReview(
                entity_type="opportunity",
                entity_id=opp.id,
                reason="Ambiguous title match test",
                priority=ReviewPriority.HIGH.value,
                status=ReviewStatus.OPEN.value,
            )
            session.add(review)

            conflict = VerificationConflict(
                opportunity_id=opp.id,
                field_name="deadline",
                status=ConflictStatus.OPEN.value,
                conflicting_values="{'source1': '2026-10-01', 'source2': '2026-10-05'}",
            )
            session.add(conflict)
            await session.commit()
            review_id = review.id
            conflict_id = conflict.id

        async with AsyncClient(transport=self.transport, base_url="http://test") as client:
            # 1. Test GET /verification/queue alias
            q_resp = await client.get("/api/v1/verification/queue")
            self.assertEqual(q_resp.status_code, 200)
            queue = q_resp.json()
            self.assertTrue(any(item["id"] == review_id for item in queue))

            # 2. Test POST /verification/queue/{id}/resolve with APPROVE
            resolve_resp = await client.post(
                f"/api/v1/verification/queue/{review_id}/resolve",
                json={"action": "APPROVE", "notes": "Manually verified"},
            )
            self.assertEqual(resolve_resp.status_code, 200)
            self.assertEqual(resolve_resp.json()["status"], ReviewStatus.APPROVED.value)

            # 3. Test POST /verification/conflicts/{id}/resolve
            conf_resp = await client.post(
                f"/api/v1/verification/conflicts/{conflict_id}/resolve",
                json={
                    "resolved_value": "2026-10-05T23:59:59Z",
                    "resolution_strategy": "MANUAL_OFFICIAL_OVERRIDE",
                    "notes": "Verified against official organizer portal",
                },
            )
            self.assertEqual(conf_resp.status_code, 200)
            conf_data = conf_resp.json()
            self.assertEqual(conf_data["status"], "resolved_manual")
            self.assertIn("Verified against official organizer portal", conf_data["resolution_notes"])
