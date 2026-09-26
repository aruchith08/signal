"""
Unit & Integration Tests for Phase 6A: Unstop Live Connector
Validates:
- Parsing valid Unstop API responses
- Handling missing optional fields gracefully
- Handling invalid JSON and unexpected structures
- Network failure resilience (timeouts, connection errors)
- Stable external identity across repeated runs
- Health check behaviour
- Connector contract verification via ConnectorContractTestMixin
- End-to-end ingestion pipeline integration with ChangeSet generation on deadline update
"""
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from httpx import Response, Request
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select

from apps.api.models.base import Base
from apps.api.models import Opportunity, ChangeSet, Source, OpportunityEvent
from apps.api.models.discovery import RawDiscovery
from connectors.unstop import UnstopConnector
from services.ingestion.pipeline import IngestionPipeline
from shared.constants import (
    ChangeType,
    DiscoveryStatus,
    OpportunityCategory,
    OpportunityStatus,
    PriorityLevel,
    SourceType,
    TrustLevel,
)
from tests.helpers.connector_contract import ConnectorContractTestMixin


SAMPLE_UNSTOP_API_RESPONSE = {
    "data": {
        "current_page": 1,
        "total": 2,
        "data": [
            {
                "id": 180100,
                "title": "Smart AI Innovation Hackathon 2026",
                "seo_url": "https://unstop.com/hackathons/smart-ai-innovation-hackathon-2026-180100",
                "public_url": "hackathons/smart-ai-innovation-hackathon-2026-180100",
                "type": "hackathons",
                "subtype": "open_innovation",
                "details": "<p>Build groundbreaking AI solutions for real-world automation challenges. Win cash prizes and mentorship.</p>",
                "region": "online",
                "start_date": "2026-09-15T10:00:00+05:30",
                "end_date": "2026-10-01T23:59:00+05:30",
                "updated_at": "2026-09-12T12:00:00+05:30",
                "organisation": {
                    "id": 9901,
                    "name": "Global Tech Institute",
                    "logoUrl": "https://cdn.unstop.com/logos/gti.png",
                    "logoUrl2": "https://cdn.unstop.com/logos/gti_large.png",
                },
                "regnRequirements": {
                    "start_regn_dt": "2026-09-15T10:00:00+05:30",
                    "end_regn_dt": "2026-10-01T23:59:00+05:30",
                    "eligibility": "Engineering and Science students (B.Tech / M.Tech / BCA)",
                    "min_team_size": 2,
                    "max_team_size": 4,
                },
                "required_skills": [
                    {"id": 1, "skill_name": "Python"},
                    {"id": 2, "skill_name": "Machine Learning"},
                ],
                "tags": [
                    {"name": "Artificial Intelligence"},
                    {"name": "Hackathon"},
                ],
                "locations": [{"city": "Bengaluru"}],
                "prizes": [
                    {"rank": "1st Prize", "cash": 100000},
                    {"rank": "Runner Up", "cash": 50000},
                ],
                "thumb": "https://cdn.unstop.com/thumbs/180100.png",
            },
            {
                "id": 180200,
                "title": "National Coding Championship Season 5",
                "seo_url": "https://unstop.com/competitions/national-coding-championship-season-5-180200",
                "public_url": "competitions/national-coding-championship-season-5-180200",
                "type": "competitions",
                "subtype": "coding_contest",
                "details": "<p>Fast-paced competitive programming contest solving algorithmic puzzles and data structure problems.</p>",
                "region": "online",
                "start_date": "2026-09-20T10:00:00+05:30",
                "end_date": "2026-10-10T18:00:00+05:30",
                "updated_at": "2026-09-12T12:00:00+05:30",
                "organisation": {
                    "id": 9902,
                    "name": "Code India Network",
                },
                "regnRequirements": {
                    "start_regn_dt": "2026-09-20T10:00:00+05:30",
                    "end_regn_dt": "2026-10-10T18:00:00+05:30",
                    "eligibility": "Open to all students",
                    "min_team_size": 1,
                    "max_team_size": 1,
                },
                "required_skills": [
                    {"skill_name": "Data Structures"},
                    {"skill_name": "Algorithms"},
                ],
                "tags": ["Coding", "Algorithms"],
                "locations": [],
                "prizes": [
                    {"rank": "Winner", "cash": 75000},
                ],
            },
        ]
    }
}


class TestUnstopConnector(unittest.IsolatedAsyncioTestCase, ConnectorContractTestMixin):
    """Unit and contract tests for the Unstop live connector."""

    def test_connector_initialization(self):
        """Verify standard connector configuration."""
        connector = UnstopConnector()
        self.assert_connector_initialization(connector)
        self.assertEqual(connector.name, "Unstop")
        self.assertEqual(connector.source_type, SourceType.API)
        self.assertEqual(connector.trust_level, TrustLevel.HIGH)
        self.assertEqual(connector.base_url, "https://unstop.com")

    @patch("services.ingestion.http_client.ResilientHTTPClient.get")
    async def test_parse_valid_response(self, mock_get):
        """Verify normal opportunity extraction from valid Unstop API payload."""
        mock_response = Response(
            status_code=200,
            json=SAMPLE_UNSTOP_API_RESPONSE,
            request=Request("GET", "https://unstop.com/api/public/opportunity/search-result"),
        )
        mock_get.return_value = mock_response

        connector = UnstopConnector(opportunity_types=["hackathons"])
        items = await connector.fetch_raw_items()

        self.assertEqual(len(items), 2)
        self.assert_raw_items_contract(items, source_name="Unstop")

        # Verify first item (Hackathon)
        item1 = items[0]
        self.assertEqual(item1.source_identifier, "unstop-180100")
        self.assertEqual(item1.title, "Smart AI Innovation Hackathon 2026")
        self.assertEqual(item1.url, "https://unstop.com/hackathons/smart-ai-innovation-hackathon-2026-180100")
        self.assertIn("Python", item1.metadata["skills"])
        self.assertEqual(item1.metadata["organization"], "Global Tech Institute")
        self.assertEqual(item1.metadata["category"], OpportunityCategory.HACKATHON.value)
        self.assertEqual(item1.metadata["mode"], "online")
        self.assertIn("Bengaluru", item1.metadata["location"])
        self.assertIsNotNone(item1.metadata["deadline_date"])
        self.assertIn("INR 100000", item1.metadata["prizes"])

        # Verify second item (Competitive Programming / Coding Contest)
        item2 = items[1]
        self.assertEqual(item2.source_identifier, "unstop-180200")
        self.assertEqual(item2.metadata["category"], OpportunityCategory.COMPETITIVE_PROGRAMMING.value)
        self.assertEqual(item2.metadata["organization"], "Code India Network")

    def test_missing_optional_fields(self):
        """Verify resilient parsing when non-mandatory fields are omitted or null."""
        connector = UnstopConnector()
        minimal_entry = {
            "id": 999999,
            "title": "Minimal Coding Quest",
            # No seo_url, details, organisation, regnRequirements, prizes, skills, etc.
        }

        item = connector._parse_item(minimal_entry, opp_type="competitions")
        self.assertIsNotNone(item)
        self.assertEqual(item.source_identifier, "unstop-999999")
        self.assertEqual(item.title, "Minimal Coding Quest")
        self.assertEqual(item.url, "https://unstop.com/o/999999")
        self.assertEqual(item.metadata["organization"], "Unstop")
        self.assertIsNone(item.metadata["deadline"])
        self.assertIsNone(item.metadata["deadline_date"])
        self.assertEqual(item.metadata["skills"], [])
        self.assertEqual(item.metadata["prizes"], "Not specified")

        # Entry with no title should return None
        no_title_entry = {"id": 12345}
        self.assertIsNone(connector._parse_item(no_title_entry))

        # Entry with no id should return None
        no_id_entry = {"title": "No ID Event"}
        self.assertIsNone(connector._parse_item(no_id_entry))

    @patch("services.ingestion.http_client.ResilientHTTPClient.get")
    async def test_invalid_response_structure(self, mock_get):
        """Verify that malformed JSON or unexpected schema fails gracefully without crashing."""
        # Malformed structure where 'data' is not a dict
        bad_response = Response(
            status_code=200,
            json={"data": "unexpected string format"},
            request=Request("GET", "https://unstop.com/api/public/opportunity/search-result"),
        )
        mock_get.return_value = bad_response

        connector = UnstopConnector(opportunity_types=["hackathons"])
        items = await connector.fetch_raw_items()
        self.assertEqual(items, [])

    @patch("services.ingestion.http_client.ResilientHTTPClient.get")
    async def test_network_failures(self, mock_get):
        """Verify network exceptions are caught safely and do not escape."""
        import httpx

        connector = UnstopConnector(opportunity_types=["hackathons"])

        # 1. Timeout
        mock_get.side_effect = httpx.TimeoutException("Connection timed out")
        items = await connector.fetch_raw_items()
        self.assertEqual(items, [])

        # 2. Network Error
        mock_get.side_effect = httpx.NetworkError("DNS resolution failure")
        items = await connector.fetch_raw_items()
        self.assertEqual(items, [])

        # 3. HTTP 500 error response
        mock_get.side_effect = None
        mock_get.return_value = Response(
            status_code=500,
            content=b"Internal Server Error",
            request=Request("GET", "https://unstop.com/api/public/opportunity/search-result"),
        )
        items = await connector.fetch_raw_items()
        self.assertEqual(items, [])

    def test_stable_identity(self):
        """Ensure repeated parsing of the same payload produces identical identifiers."""
        connector = UnstopConnector()
        entry = SAMPLE_UNSTOP_API_RESPONSE["data"]["data"][0]

        item1 = connector._parse_item(entry)
        item2 = connector._parse_item(entry)

        self.assertIsNotNone(item1)
        self.assertIsNotNone(item2)
        self.assertEqual(item1.source_identifier, item2.source_identifier)
        self.assertEqual(item1.url, item2.url)
        self.assertEqual(item1.canonical_url(), item2.canonical_url())
        self.assertEqual(item1.metadata["external_id"], item2.metadata["external_id"])

    @patch("services.ingestion.http_client.ResilientHTTPClient.get")
    async def test_health_check(self, mock_get):
        """Verify health check logic."""
        connector = UnstopConnector()

        # Healthy
        mock_get.return_value = Response(
            status_code=200,
            json={"data": {"total": 100}},
            request=Request("GET", "https://unstop.com/api/public/opportunity/search-result"),
        )
        self.assertTrue(await connector.health_check())

        # Degraded / Server error
        mock_get.return_value = Response(
            status_code=503,
            content=b"Service Unavailable",
            request=Request("GET", "https://unstop.com/api/public/opportunity/search-result"),
        )
        self.assertFalse(await connector.health_check())


class TestUnstopPipelineIntegration(unittest.IsolatedAsyncioTestCase):
    """
    Integration test proving:
    Mock UNSTOP Response -> UnstopConnector -> IngestionPipeline -> RawDiscovery -> LifecycleEngine -> Opportunity
    Then simulate updated deadline -> OpportunityChangeDetector -> ChangeSet created!
    """

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

    @patch("services.ingestion.http_client.ResilientHTTPClient.get")
    async def test_unstop_ingestion_and_changeset_generation(self, mock_get):
        """Verify end-to-end ingestion and structured ChangeSet creation on opportunity updates."""
        connector = UnstopConnector(opportunity_types=["hackathons"])

        # Initial payload: Hackathon with deadline 2026-10-01
        initial_payload = {
            "data": {
                "total": 1,
                "data": [
                    {
                        "id": 900100,
                        "title": "Autonomous AI Robotics Hackathon",
                        "seo_url": "https://unstop.com/hackathons/autonomous-ai-robotics-hackathon-900100",
                        "type": "hackathons",
                        "details": "Flagship robotics and AI challenge for engineering students. Win cash prizes and internship offers.",
                        "region": "online",
                        "end_date": "2026-10-01T23:59:00+05:30",
                        "organisation": {"name": "Robotics Consortium"},
                        "regnRequirements": {
                            "start_regn_dt": "2026-09-10T00:00:00+05:30",
                            "end_regn_dt": "2026-10-01T23:59:00+05:30",
                            "eligibility": "All undergraduate students",
                        },
                        "required_skills": [{"skill_name": "Robotics"}, {"skill_name": "Python"}],
                        "prizes": [{"rank": "Winner", "cash": 100000}],
                    }
                ]
            }
        }

        mock_get.return_value = Response(
            status_code=200,
            json=initial_payload,
            request=Request("GET", "https://unstop.com/api/public/opportunity/search-result"),
        )

        # 1. Run Initial Ingestion
        async with self.session_factory() as session:
            pipeline = IngestionPipeline(session)
            created_opps = await pipeline.process_connector(connector)
            self.assertEqual(len(created_opps), 1)

            opp = created_opps[0]
            self.assertEqual(opp.title, "Autonomous AI Robotics Hackathon")
            self.assertEqual(opp.category, OpportunityCategory.HACKATHON.value)
            self.assertEqual(opp.status, OpportunityStatus.ACTIVE.value)
            initial_opp_id = opp.id

            # Verify OpportunityEvent recorded with deadline_date
            event_stmt = select(OpportunityEvent).where(OpportunityEvent.opportunity_id == initial_opp_id)
            events = (await session.execute(event_stmt)).scalars().all()
            self.assertTrue(len(events) >= 1)
            self.assertIsNotNone(events[0].deadline_date)

            # Verify RawDiscovery recorded and transitioned to PROCESSED
            disc_stmt = select(RawDiscovery).where(RawDiscovery.external_id == "unstop-900100")
            disc = (await session.execute(disc_stmt)).scalar_one_or_none()
            self.assertIsNotNone(disc)
            self.assertEqual(disc.opportunity_id, initial_opp_id)
            self.assertEqual(disc.status, DiscoveryStatus.PROCESSED.value)

            # Verify 0 ChangeSets generated on initial opportunity creation
            cs_stmt = select(ChangeSet).where(ChangeSet.opportunity_id == initial_opp_id)
            initial_changesets = (await session.execute(cs_stmt)).scalars().all()
            self.assertEqual(len(initial_changesets), 0)

        # 2. Simulate second run with EXTENDED DEADLINE (deadline changed from 2026-10-01 to 2026-10-25)
        updated_payload = {
            "data": {
                "total": 1,
                "data": [
                    {
                        "id": 900100,
                        "title": "Autonomous AI Robotics Hackathon",
                        "seo_url": "https://unstop.com/hackathons/autonomous-ai-robotics-hackathon-900100",
                        "type": "hackathons",
                        "details": "Flagship robotics and AI challenge for engineering students. Win cash prizes and internship offers. Deadline extended!",
                        "region": "online",
                        "end_date": "2026-10-25T23:59:00+05:30",
                        "organisation": {"name": "Robotics Consortium"},
                        "regnRequirements": {
                            "start_regn_dt": "2026-09-10T00:00:00+05:30",
                            "end_regn_dt": "2026-10-25T23:59:00+05:30",
                            "eligibility": "All undergraduate students",
                        },
                        "required_skills": [{"skill_name": "Robotics"}, {"skill_name": "Python"}],
                        "prizes": [{"rank": "Winner", "cash": 100000}],
                    }
                ]
            }
        }

        mock_get.return_value = Response(
            status_code=200,
            json=updated_payload,
            request=Request("GET", "https://unstop.com/api/public/opportunity/search-result"),
        )

        async with self.session_factory() as session:
            pipeline = IngestionPipeline(session)
            processed_opps = await pipeline.process_connector(connector)
            self.assertEqual(len(processed_opps), 1)

            updated_opp = processed_opps[0]
            self.assertEqual(updated_opp.id, initial_opp_id, "Must resolve to existing opportunity ID")

            # Verify structured ChangeSet was generated
            cs_stmt = select(ChangeSet).where(ChangeSet.opportunity_id == initial_opp_id)
            changesets = (await session.execute(cs_stmt)).scalars().all()
            self.assertTrue(len(changesets) >= 1, "ChangeSet must be generated for modified opportunity")

            deadline_cs = [cs for cs in changesets if cs.field_name == "deadline_date"]
            self.assertEqual(len(deadline_cs), 1, "Expected 1 ChangeSet for deadline_date")
            cs = deadline_cs[0]
            self.assertEqual(cs.change_type, ChangeType.DEADLINE_CHANGED.value)
            self.assertEqual(cs.importance, PriorityLevel.CRITICAL.value)
            self.assertIn("2026-10-01", cs.previous_value)
            self.assertIn("2026-10-25", cs.new_value)


if __name__ == "__main__":
    unittest.main()
