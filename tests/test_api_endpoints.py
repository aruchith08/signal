"""
Automated Verification of FastAPI REST Endpoints for SIGNAL
"""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from apps.api.main import app
from apps.api.database import get_db, Base


class TestAPIEndpoints(unittest.IsolatedAsyncioTestCase):
    """Test suite for FastAPI REST endpoints."""

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


    async def test_health_endpoint(self):
        """Verify GET /api/v1/health returns healthy status."""
        async with AsyncClient(transport=self.transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/health")
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertEqual(data["status"], "healthy")
            self.assertEqual(data["app_name"], "SIGNAL")
            self.assertEqual(data["ai_gateway"]["primary_provider"], "mock")

    async def test_organization_crud(self):
        """Verify POST and GET /api/v1/organizations."""
        async with AsyncClient(transport=self.transport, base_url="http://test") as client:
            # Create organization
            org_payload = {
                "name": "Google",
                "website": "https://buildyourfuture.withgoogle.com",
                "is_verified": True,
            }
            resp = await client.post("/api/v1/organizations", json=org_payload)
            self.assertEqual(resp.status_code, 201)
            org = resp.json()
            self.assertEqual(org["name"], "Google")
            self.assertEqual(org["slug"], "google")

            # List organizations
            resp = await client.get("/api/v1/organizations?search=Google")
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertGreaterEqual(data["total"], 1)

    async def test_source_registration(self):
        """Verify POST and GET /api/v1/sources."""
        async with AsyncClient(transport=self.transport, base_url="http://test") as client:
            source_payload = {
                "name": "Codeforces Contests",
                "category": "competitive_programming",
                "source_type": "api",
                "base_url": "https://codeforces.com/api",
                "monitor_frequency_minutes": 30,
                "priority": 1,
                "trust_level": "high",
            }
            resp = await client.post("/api/v1/sources", json=source_payload)
            self.assertEqual(resp.status_code, 201)
            source = resp.json()
            self.assertEqual(source["slug"], "codeforces-contests")

            # List sources
            resp = await client.get("/api/v1/sources?category=competitive_programming")
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertGreaterEqual(data["total"], 1)

    async def test_opportunity_creation_and_query(self):
        """Verify POST and GET /api/v1/opportunities."""
        async with AsyncClient(transport=self.transport, base_url="http://test") as client:
            opp_payload = {
                "title": "Microsoft Imagine Cup 2026",
                "category": "hackathon",
                "status": "registration_open",
                "verification_status": "verified",
                "confidence_score": 98,
                "official": True,
                "eligibility": "Students aged 16+ enrolled in university",
                "target_audience": "Tech builders, AI developers",
                "raw_content": "Microsoft Imagine Cup 2026 global student technology competition is now live.",
                "summary": "Premier global technology competition for student innovators.",
                "events": [
                    {
                        "event_type": "registration_open",
                        "title": "Imagine Cup Submissions Open",
                        "is_critical": False,
                    }
                ],
            }
            resp = await client.post("/api/v1/opportunities", json=opp_payload)
            self.assertEqual(resp.status_code, 201)
            opp = resp.json()
            self.assertEqual(opp["title"], "Microsoft Imagine Cup 2026")
            self.assertEqual(len(opp["events"]), 1)

            # Retrieve by ID
            opp_id = opp["id"]
            resp = await client.get(f"/api/v1/opportunities/{opp_id}")
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.json()["id"], opp_id)

    async def test_trigger_mock_ingestion_api(self):
        """Verify POST /api/v1/ingestion/trigger-mock triggers pipeline and creates opportunities."""
        async with AsyncClient(transport=self.transport, base_url="http://test") as client:
            resp = await client.post("/api/v1/ingestion/trigger-mock")
            self.assertEqual(resp.status_code, 200)
            opportunities = resp.json()
            self.assertGreaterEqual(len(opportunities), 3)


if __name__ == "__main__":
    unittest.main()
