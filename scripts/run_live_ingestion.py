"""
SIGNAL 📡 — Live Ingestion Execution & Verification CLI Script
Polls real internet sources (Codeforces, GitHub Blog, Smart India Hackathon),
processes them through the complete normalization and change detection pipeline,
and reports audit results.
"""
import asyncio
import logging
import sys
from pathlib import Path

# Add project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select, func
from apps.api.database import AsyncSessionLocal, init_db, engine
from apps.api.models import Opportunity, Organization, Source
from apps.api.models.discovery import RawDiscovery
from apps.api.models.event import OpportunityEvent
from apps.api.models.alias import OpportunityAlias
from connectors.competitive_programming.codeforces import CodeforcesConnector
from connectors.companies.github_blog import GitHubBlogConnector
from connectors.government.sih import SIHConnector
from services.ingestion.pipeline import IngestionPipeline

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("signal.live_run")


async def main():
    print("=" * 80)
    print("SIGNAL - Phase 1A: Live Ingestion Verification")
    print("=" * 80)


    await init_db()

    connectors = [
        CodeforcesConnector(include_recent_finished=5),
        GitHubBlogConnector(max_items=10),
        SIHConnector(max_items=15),
    ]

    async with AsyncSessionLocal() as session:
        pipeline = IngestionPipeline(session)


        for conn in connectors:
            print(f"\n[+] Probing health for connector: {conn.name} ({conn.source_type.value})...")
            healthy = await conn.health_check()
            print(f"    Health check: {'HEALTHY (ONLINE)' if healthy else 'FAILED (OFFLINE)'}")

            if not healthy:
                print(f"    Skipping {conn.name} due to health check failure.")
                continue

            print(f"[*] Executing live ingestion pipeline for: {conn.name}...")
            opportunities = await pipeline.process_connector(conn)
            print(f"    Ingested / Updated Opportunities: {len(opportunities)}")
            for opp in opportunities[:3]:
                print(f"      - [{opp.category.upper()}] {opp.title} ({opp.application_url})")

        print("\n" + "=" * 80)
        print("AUDIT SUMMARY (From Live Database - Phase 1A + Phase 1B)")
        print("=" * 80)

        total_disc = (await session.execute(select(func.count(RawDiscovery.id)))).scalar_one()
        total_opps = (await session.execute(select(func.count(Opportunity.id)))).scalar_one()
        total_orgs = (await session.execute(select(func.count(Organization.id)))).scalar_one()
        total_sources = (await session.execute(select(func.count(Source.id)))).scalar_one()
        total_events = (await session.execute(select(func.count(OpportunityEvent.id)))).scalar_one()
        total_aliases = (await session.execute(select(func.count(OpportunityAlias.id)))).scalar_one()

        print(f"Total Raw Discoveries:           {total_disc}")
        print(f"Total Canonical Opportunities:   {total_opps}")
        print(f"Total Lifecycle Events Logged:   {total_events}")
        print(f"Total Opportunity Aliases:       {total_aliases}")
        print(f"Total Organizations Tracked:     {total_orgs}")
        print(f"Total Sources Monitored:         {total_sources}")

        print("\n[Discovery Classification Breakdown]")
        cls_counts = (
            await session.execute(
                select(RawDiscovery.content_classification, func.count(RawDiscovery.id)).group_by(RawDiscovery.content_classification)
            )
        ).all()
        for classification, count in cls_counts:
            print(f"  - {classification or 'unclassified'}: {count}")

        print("\n[Audit Trail Sample: Last 8 Discoveries]")
        stmt = select(RawDiscovery).order_by(RawDiscovery.fetched_at.desc()).limit(8)
        recent_discoveries = (await session.execute(stmt)).scalars().all()
        for d in recent_discoveries:
            print(f"  [{d.status.upper()} | {d.content_classification or 'unknown'}] {d.raw_title[:55]}... -> opp_id: {d.opportunity_id}")
            print(f"    Hash: {d.content_hash[:12]}... | Canonical URL: {d.canonical_url[:65]}...")

        # Evaluate watches on any existing discoveries that lack watch matches
        all_discs = (await session.execute(select(RawDiscovery))).scalars().all()
        for d in all_discs:
            await pipeline.watch_engine.evaluate_discovery(d)
        await session.commit()

        # -------------------------------------------------------------------------
        # PROGRAM WATCH SUMMARY (Phase 1C-A)
        # -------------------------------------------------------------------------
        from apps.api.models.program_watch import ProgramWatch, ProgramWatchMatch
        from services.watch.scoring import WatchMatchScorer

        active_watches_count = (
            await session.execute(select(func.count(ProgramWatch.id)).where(ProgramWatch.is_active.is_(True)))
        ).scalar_one()

        print("\n" + "=" * 80)
        print("PROGRAM WATCH SUMMARY")
        print("=" * 80)
        print(f"Active Watches:\n{active_watches_count}\n")
        print("WATCH MATCHES")

        watches = (
            await session.execute(select(ProgramWatch).order_by(ProgramWatch.priority.asc(), ProgramWatch.name.asc()))
        ).scalars().all()

        current_priority = None
        priority_emojis = {
            "critical": "🔴 CRITICAL",
            "high": "🟠 HIGH",
            "medium": "🟢 MEDIUM",
            "low": "⚪ LOW",
        }

        for w in watches:
            if w.priority != current_priority:
                current_priority = w.priority
                print(f"\n{priority_emojis.get(current_priority, current_priority.upper())}")

            m_count = (
                await session.execute(
                    select(func.count(ProgramWatchMatch.id)).where(ProgramWatchMatch.program_watch_id == w.id)
                )
            ).scalar_one()
            print(f"{w.name}\nMatches: {m_count}\n")

        print("-" * 80)
        print("HIGH CONFIDENCE MATCHES")
        high_matches = (
            await session.execute(
                select(ProgramWatchMatch)
                .where(ProgramWatchMatch.match_score >= WatchMatchScorer.CONFIDENCE_HIGH_THRESHOLD)
                .order_by(ProgramWatchMatch.match_score.desc())
                .limit(5)
            )
        ).scalars().all()

        for hm in high_matches:
            watch_name = (
                await session.execute(select(ProgramWatch.name).where(ProgramWatch.id == hm.program_watch_id))
            ).scalar_one()
            disc_title = (
                await session.execute(select(RawDiscovery.raw_title).where(RawDiscovery.id == hm.raw_discovery_id))
            ).scalar_one()
            print(f"  [{hm.match_score:.2f} | {hm.match_level}] {watch_name} <- '{disc_title[:50]}...'")

        print("-" * 80)
        print("TOTAL")
        total_matches = (await session.execute(select(func.count(ProgramWatchMatch.id)))).scalar_one()
        high_count = (
            await session.execute(
                select(func.count(ProgramWatchMatch.id)).where(
                    ProgramWatchMatch.match_score >= WatchMatchScorer.CONFIDENCE_HIGH_THRESHOLD
                )
            )
        ).scalar_one()
        med_count = (
            await session.execute(
                select(func.count(ProgramWatchMatch.id)).where(
                    (ProgramWatchMatch.match_score >= WatchMatchScorer.CONFIDENCE_MEDIUM_THRESHOLD)
                    & (ProgramWatchMatch.match_score < WatchMatchScorer.CONFIDENCE_HIGH_THRESHOLD)
                )
            )
        ).scalar_one()
        low_count = (
            await session.execute(
                select(func.count(ProgramWatchMatch.id)).where(
                    ProgramWatchMatch.match_score < WatchMatchScorer.CONFIDENCE_MEDIUM_THRESHOLD
                )
            )
        ).scalar_one()

        print(f"Watch Matches: {total_matches}")
        print(f"High Confidence: {high_count}")
        print(f"Medium Confidence: {med_count}")
        print(f"Low Confidence: {low_count}")
        print("=" * 80)

    await engine.dispose()
    print("\n[SUCCESS] Live Ingestion Run Completed Successfully!\n")



if __name__ == "__main__":
    asyncio.run(main())
