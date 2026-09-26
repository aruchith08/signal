"""
Mock Source Connector — Generates sample announcements for testing the ingestion pipeline
"""
from datetime import datetime, timezone
from typing import List
from connectors.base_connector import BaseConnector, RawItem
from shared.constants import OpportunityCategory, SourceType, TrustLevel


class MockConnector(BaseConnector):
    """Generates realistic opportunities across categories for testing."""

    def __init__(self, name: str = "mock_announcements", is_active: bool = True):
        super().__init__(
            name=name,
            category=OpportunityCategory.COMPETITIVE_PROGRAMMING,
            source_type=SourceType.PUBLIC_FEED,
            trust_level=TrustLevel.HIGH,
            base_url="https://mock-sources.signal.internal",
            is_active=is_active,
        )

    async def health_check(self) -> bool:
        return True

    async def fetch_raw_items(self) -> List[RawItem]:
        now = datetime.now(timezone.utc)
        return [
            RawItem(
                title="TCS CodeVita Season 12 — Global Coding Contest Announced",
                url="https://campus.tcs.com/codevita-season-12",
                content="""
                Tata Consultancy Services (TCS) invites engineering and science students worldwide
                to participate in TCS CodeVita Season 12, the world's largest competitive programming contest.
                Registrations are now open. Top performers receive cash prizes up to $20,000 and direct
                technical interview opportunities for TCS Digital and TCS Innovator roles.
                Eligibility: Students graduating in 2025, 2026, 2027 from B.Tech, M.Tech, BCA, MCA.
                Registration Deadline: October 15, 2026. Round 1 contest scheduled for October 24, 2026.
                """,
                source_name="TCS Official Portal",
                source_identifier="tcs_codevita_s12",
                published_at=now,
                metadata={"category": OpportunityCategory.COMPETITIVE_PROGRAMMING.value, "official": True},
            ),
            RawItem(
                title="Smart India Hackathon (SIH) 2026 — Problem Statements Released",
                url="https://www.sih.gov.in/sih2026",
                content="""
                Ministry of Education's Innovation Cell (MIC) and AICTE announce Smart India Hackathon 2026.
                Over 250 problem statements from 60+ Central Ministries, Departments, and State Governments
                are now live. College SPOC registration and team idea submissions are open until November 5, 2026.
                Categories: Software and Hardware editions.
                Eligibility: Regular enrolled students of AICTE / UGC approved institutions in teams of 6 members.
                Prizes: Rs 1,00,000 per winning problem statement.
                """,
                source_name="MoE / AICTE SIH Portal",
                source_identifier="aicte_sih_2026",
                published_at=now,
                metadata={"category": OpportunityCategory.GOVERNMENT.value, "official": True},
            ),
            RawItem(
                title="Flipkart GRiD 6.0 — Engineering & Robotics Challenge",
                url="https://unstop.com/competitions/flipkart-grid-6-engineering-campus-challenge",
                content="""
                Flipkart GRiD 6.0 is Flipkart's flagship campus challenge for engineering students.
                Tracks: Software Development, Information Security, and Robotics.
                Features exciting real-world problem statements, PPI opportunities for SDE-1 and SDE Internships,
                and total prize pool of INR 5,25,000.
                Eligibility: B.Tech / B.E / M.Tech students from batch of 2025, 2026, 2027, 2028.
                Registration closing date: November 1, 2026.
                """,
                source_name="Unstop Flipkart Portal",
                source_identifier="flipkart_grid_6",
                published_at=now,
                metadata={"category": OpportunityCategory.MAJOR_COMPANY_PROGRAM.value, "official": True},
            ),
        ]
