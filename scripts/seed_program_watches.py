"""
SIGNAL 📡 — Seed Program Watch Registry Script
Seeds 15 curated program watches across CRITICAL, HIGH, and MEDIUM priority tiers.
Idempotent: Safe to run multiple times without duplicating entries.
"""
import asyncio
import logging
import sys
from pathlib import Path

# Add project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select
from apps.api.database import AsyncSessionLocal, init_db, engine
from apps.api.models.organization import Organization
from apps.api.models.program_watch import (
    ProgramWatch,
    ProgramWatchAlias,
    ProgramWatchKeyword,
)
from shared.constants import WatchPriority
from shared.utils import normalize_title, slugify

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("signal.seed_watches")

CURATED_WATCHES = [
    # -------------------------------------------------------------------------
    # 🔴 CRITICAL
    # -------------------------------------------------------------------------
    {
        "name": "Smart India Hackathon",
        "canonical_name": "smart india hackathon",
        "organization": "Government of India / SIH",
        "description": "World's biggest open innovation model and nationwide student hackathon by MoE & AICTE.",
        "priority": WatchPriority.CRITICAL.value,
        "aliases": ["SIH", "Smart India Hackathon", "SIH 2026"],
        "keywords": [
            ("Smart India Hackathon", 1.0, True),
            ("SIH", 1.0, True),
            ("Problem Statement", 0.6, True),
            ("Hackathon", 0.3, False),
            ("AICTE", 0.4, False),
        ],
    },
    {
        "name": "TCS CodeVita",
        "canonical_name": "tcs codevita",
        "organization": "TCS",
        "description": "Guinness World Record holding flagship global competitive programming contest by TCS.",
        "priority": WatchPriority.CRITICAL.value,
        "aliases": ["CodeVita", "TCS CodeVita", "CodeVita Season 13"],
        "keywords": [
            ("CodeVita", 1.0, True),
            ("TCS CodeVita", 1.0, True),
            ("TCS", 0.4, False),
            ("Programming Competition", 0.4, False),
            ("Campus Commune", 0.5, True),
        ],
    },
    {
        "name": "Google Summer of Code",
        "canonical_name": "google summer of code",
        "organization": "Google",
        "description": "Global online program focused on bringing new contributors into open source software development.",
        "priority": WatchPriority.CRITICAL.value,
        "aliases": ["GSoC", "Google Summer of Code", "GSoC 2026"],
        "keywords": [
            ("GSoC", 1.0, True),
            ("Google Summer of Code", 1.0, True),
            ("Summer of Code", 0.8, True),
            ("Open Source Mentorship", 0.5, True),
            ("Google", 0.3, False),
        ],
    },
    {
        "name": "HackWithInfy",
        "canonical_name": "hackwithinfy",
        "organization": "Infosys",
        "description": "Flagship annual coding competition for engineering students across India hosted by Infosys.",
        "priority": WatchPriority.CRITICAL.value,
        "aliases": ["HackWithInfy", "Hack With Infy"],
        "keywords": [
            ("HackWithInfy", 1.0, True),
            ("Hack With Infy", 1.0, True),
            ("Infosys", 0.4, False),
            ("Coding Contest", 0.3, False),
        ],
    },
    {
        "name": "Flipkart GRiD",
        "canonical_name": "flipkart grid",
        "organization": "Flipkart",
        "description": "Flagship campus challenge bringing tech, robotics, and supply chain problem statements.",
        "priority": WatchPriority.CRITICAL.value,
        "aliases": ["Flipkart GRiD", "Flipkart GRiD 6.0", "Flipkart GRiD 7.0"],
        "keywords": [
            ("Flipkart GRiD", 1.0, True),
            ("GRiD 6.0", 0.9, True),
            ("GRiD 7.0", 0.9, True),
            ("Flipkart", 0.4, False),
            ("Campus Challenge", 0.3, False),
        ],
    },
    {
        "name": "Microsoft Imagine Cup",
        "canonical_name": "microsoft imagine cup",
        "organization": "Microsoft",
        "description": "Premier global student technology competition empowering student entrepreneurs with AI.",
        "priority": WatchPriority.CRITICAL.value,
        "aliases": ["Imagine Cup", "Microsoft Imagine Cup"],
        "keywords": [
            ("Imagine Cup", 1.0, True),
            ("Microsoft Imagine Cup", 1.0, True),
            ("Microsoft", 0.4, False),
            ("Student Competition", 0.3, False),
        ],
    },
    # -------------------------------------------------------------------------
    # 🟠 HIGH
    # -------------------------------------------------------------------------
    {
        "name": "Google Solution Challenge",
        "canonical_name": "google solution challenge",
        "organization": "Google",
        "description": "Annual contest inviting university students to solve for UN Sustainable Development Goals using Google tech.",
        "priority": WatchPriority.HIGH.value,
        "aliases": ["Solution Challenge", "Google Solution Challenge", "GDSC Solution Challenge"],
        "keywords": [
            ("Solution Challenge", 0.9, True),
            ("Google Solution Challenge", 1.0, True),
            ("GDSC", 0.7, True),
        ],
    },
    {
        "name": "Amazon ML Challenge",
        "canonical_name": "amazon ml challenge",
        "organization": "Amazon",
        "description": "Premier machine learning challenge inviting students to solve real-world industry AI problems.",
        "priority": WatchPriority.HIGH.value,
        "aliases": ["Amazon ML Challenge"],
        "keywords": [
            ("Amazon ML Challenge", 1.0, True),
            ("Amazon ML", 0.8, True),
            ("Amazon", 0.4, False),
            ("Machine Learning", 0.3, False),
        ],
    },
    {
        "name": "Kaggle Competitions",
        "canonical_name": "kaggle competition",
        "organization": "Kaggle",
        "description": "Global competitive machine learning and data science community challenges.",
        "priority": WatchPriority.HIGH.value,
        "aliases": ["Kaggle Competitions", "Kaggle Contest"],
        "keywords": [
            ("Kaggle", 1.0, True),
            ("Kaggle Competition", 1.0, True),
            ("Data Science Challenge", 0.4, False),
        ],
    },
    {
        "name": "HackerRank Competitions",
        "canonical_name": "hackerrank competition",
        "organization": "HackerRank",
        "description": "Curated coding challenges, hiring contests, and hackathons hosted on HackerRank.",
        "priority": WatchPriority.HIGH.value,
        "aliases": ["HackerRank Contest", "HackerRank Competitions"],
        "keywords": [
            ("HackerRank", 1.0, True),
            ("Coding Contest", 0.3, False),
        ],
    },
    {
        "name": "HackerEarth Challenges",
        "canonical_name": "hackerearth challenge",
        "organization": "HackerEarth",
        "description": "Premier developer hackathons, coding contests, and hiring challenges.",
        "priority": WatchPriority.HIGH.value,
        "aliases": ["HackerEarth Challenge", "HackerEarth Hackathon"],
        "keywords": [
            ("HackerEarth", 1.0, True),
            ("Developer Challenge", 0.3, False),
        ],
    },
    {
        "name": "CodeChef Starters",
        "canonical_name": "codechef starters",
        "organization": "CodeChef",
        "description": "Bi-weekly algorithmic competitive programming contest for beginner and intermediate coders.",
        "priority": WatchPriority.HIGH.value,
        "aliases": ["Starters", "CodeChef Starters"],
        "keywords": [
            ("CodeChef Starters", 1.0, True),
            ("CodeChef", 0.8, True),
            ("Starters", 0.7, True),
        ],
    },
    # -------------------------------------------------------------------------
    # 🟢 MEDIUM
    # -------------------------------------------------------------------------
    {
        "name": "Codeforces Contests",
        "canonical_name": "codeforces contest",
        "organization": "Codeforces",
        "description": "Official rated competitive programming rounds (Div. 1, Div. 2, Div. 3, Div. 4).",
        "priority": WatchPriority.MEDIUM.value,
        "aliases": ["Codeforces Round", "Codeforces Contest"],
        "keywords": [
            ("Codeforces", 1.0, True),
            ("Codeforces Round", 1.0, True),
            ("Div. 1", 0.4, False),
            ("Div. 2", 0.4, False),
        ],
    },
    {
        "name": "AtCoder Contests",
        "canonical_name": "atcoder contest",
        "organization": "AtCoder",
        "description": "Renowned algorithmic programming contests from Japan including ABC, ARC, and AGC.",
        "priority": WatchPriority.MEDIUM.value,
        "aliases": ["AtCoder Beginner Contest", "AtCoder Regular Contest", "AtCoder Contest"],
        "keywords": [
            ("AtCoder", 1.0, True),
            ("AtCoder Beginner Contest", 1.0, True),
        ],
    },
    {
        "name": "Major League Hacking (MLH)",
        "canonical_name": "mlh hackathon",
        "organization": "Major League Hacking",
        "description": "Official student hackathon league powering hundreds of student events globally.",
        "priority": WatchPriority.MEDIUM.value,
        "aliases": ["MLH", "Major League Hacking", "MLH Season"],
        "keywords": [
            ("MLH", 1.0, True),
            ("Major League Hacking", 1.0, True),
            ("Hackathon Season", 0.4, False),
        ],
    },
]


async def seed_program_watches():
    await init_db()
    logger.info("Seeding curated Program Watch Registry...")

    async with AsyncSessionLocal() as session:
        created_watches = 0
        updated_watches = 0

        for item in CURATED_WATCHES:
            # 1. Resolve Organization
            org_name = item["organization"]
            org_slug = slugify(org_name)
            org_stmt = select(Organization).where(Organization.slug == org_slug)
            org = (await session.execute(org_stmt)).scalars().first()

            if not org:
                org = Organization(name=org_name, slug=org_slug, is_verified=True)
                session.add(org)
                await session.flush()

            # 2. Resolve ProgramWatch
            norm_canonical = normalize_title(item["canonical_name"])
            watch_stmt = select(ProgramWatch).where(
                (ProgramWatch.canonical_name == norm_canonical) | (ProgramWatch.name == item["name"])
            )
            watch = (await session.execute(watch_stmt)).scalars().first()

            if not watch:
                watch = ProgramWatch(
                    name=item["name"],
                    canonical_name=norm_canonical,
                    organization_id=org.id,
                    description=item.get("description"),
                    priority=item["priority"],
                    is_active=True,
                )
                session.add(watch)
                await session.flush()
                created_watches += 1
                logger.info(f"[+] Created ProgramWatch: {watch.name} (Priority: {watch.priority})")
            else:
                watch.priority = item["priority"]
                watch.description = item.get("description") or watch.description
                watch.is_active = True
                updated_watches += 1
                logger.info(f"[*] Found existing ProgramWatch: {watch.name} (ID: {watch.id})")

            # 3. Add Aliases (Idempotently)
            for alias_text in item.get("aliases", []):
                norm_alias = normalize_title(alias_text)
                alias_stmt = select(ProgramWatchAlias).where(
                    ProgramWatchAlias.program_watch_id == watch.id,
                    ProgramWatchAlias.normalized_alias == norm_alias,
                )
                existing_alias = (await session.execute(alias_stmt)).scalars().first()
                if not existing_alias:
                    new_alias = ProgramWatchAlias(
                        program_watch_id=watch.id,
                        alias=alias_text,
                        normalized_alias=norm_alias,
                    )
                    session.add(new_alias)

            # 4. Add Keywords (Idempotently)
            for kw_text, weight, is_distinctive in item.get("keywords", []):
                norm_kw = normalize_title(kw_text)
                kw_stmt = select(ProgramWatchKeyword).where(
                    ProgramWatchKeyword.program_watch_id == watch.id,
                    ProgramWatchKeyword.normalized_keyword == norm_kw,
                )
                existing_kw = (await session.execute(kw_stmt)).scalars().first()
                if not existing_kw:
                    new_kw = ProgramWatchKeyword(
                        program_watch_id=watch.id,
                        keyword=kw_text,
                        normalized_keyword=norm_kw,
                        weight=weight,
                        is_distinctive=is_distinctive,
                    )
                    session.add(new_kw)

            await session.flush()

        await session.commit()
        logger.info(
            f"Registry seed complete! Created: {created_watches}, Updated/Verified: {updated_watches} watches."
        )

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed_program_watches())
