"""
SIGNAL 📡 — Organization Aliases Seed Script
Idempotently populates known organization aliases to improve entity resolution.
"""
import asyncio
import logging
import os
import sys
from pathlib import Path

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select
from apps.api.database import AsyncSessionLocal
from apps.api.models.organization import Organization
from apps.api.models.organization_alias import OrganizationAlias
from shared.utils import slugify

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("signal.seed.org_aliases")

SEED_ALIASES = [
    {
        "org_name": "Tata Consultancy Services",
        "org_slug": "tata-consultancy-services",
        "aliases": ["TCS", "Tata Consultancy Services Limited", "TCS NextStep", "TCS iON"],
    },
    {
        "org_name": "Ministry of Education & AICTE",
        "org_slug": "aicte",
        "aliases": ["AICTE", "All India Council for Technical Education", "MoE Innovation Cell", "MIC"],
    },
    {
        "org_name": "Ministry of Electronics and Information Technology",
        "org_slug": "meity",
        "aliases": ["MeitY", "Ministry of Electronics & IT", "Digital India"],
    },
    {
        "org_name": "Google",
        "org_slug": "google",
        "aliases": ["Google LLC", "Google Open Source", "Google Developers", "Google Summer of Code"],
    },
    {
        "org_name": "Microsoft",
        "org_slug": "microsoft",
        "aliases": ["Microsoft Corporation", "Microsoft Student Developer", "Microsoft Imagine Cup"],
    },
    {
        "org_name": "Flipkart",
        "org_slug": "flipkart",
        "aliases": ["Flipkart Internet Private Limited", "Flipkart GRiD", "Flipkart Careers"],
    },
    {
        "org_name": "Government of India",
        "org_slug": "government-of-india",
        "aliases": ["MyGov", "MyGov India", "Government of India Initiatives", "Innovate India"],
    },
    {
        "org_name": "Major League Hacking",
        "org_slug": "mlh",
        "aliases": ["MLH", "Major League Hacking Season", "MLH Hackathons"],
    },
    {
        "org_name": "CodeChef",
        "org_slug": "codechef",
        "aliases": ["CodeChef Challenges", "CodeChef Contests", "Directi CodeChef"],
    },
    {
        "org_name": "HackerRank",
        "org_slug": "hackerrank",
        "aliases": ["HackerRank Contests", "HackerRank Competitions", "InterviewStreet"],
    },
    {
        "org_name": "LeetCode",
        "org_slug": "leetcode",
        "aliases": ["LeetCode Contests", "LeetCode Weekly", "LeetCode Biweekly"],
    },
]


async def seed_organization_aliases():
    async with AsyncSessionLocal() as session:
        created_orgs = 0
        created_aliases = 0

        for item in SEED_ALIASES:
            # 1. Ensure Organization exists
            stmt = select(Organization).where(Organization.slug == item["org_slug"])
            org = (await session.execute(stmt)).scalars().first()
            if not org:
                org = Organization(
                    name=item["org_name"],
                    slug=item["org_slug"],
                    is_verified=True,
                )
                session.add(org)
                await session.flush()
                created_orgs += 1

            # 2. Add Aliases
            for alias in item["aliases"]:
                clean_alias = alias.strip()
                norm_alias = slugify(clean_alias)
                check_stmt = select(OrganizationAlias).where(
                    OrganizationAlias.organization_id == org.id,
                    OrganizationAlias.alias == clean_alias,
                )
                existing = (await session.execute(check_stmt)).scalars().first()
                if not existing:
                    alias_record = OrganizationAlias(
                        organization_id=org.id,
                        alias=clean_alias,
                        normalized_alias=norm_alias,
                    )
                    session.add(alias_record)
                    created_aliases += 1

        await session.commit()
        logger.info(
            f"[Seed] Completed organization aliases seeding. "
            f"Created {created_orgs} organizations, {created_aliases} aliases."
        )


if __name__ == "__main__":
    asyncio.run(seed_organization_aliases())
