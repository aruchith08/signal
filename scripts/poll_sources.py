"""
SIGNAL 📡 — Source Polling Runner & Ingestion CLI
Polls monitored opportunity sources based on SourceRegistry definitions, policies, or flags.

Usage:
    python scripts/poll_sources.py --source all
    python scripts/poll_sources.py --source codechef
    python scripts/poll_sources.py --priority high
    python scripts/poll_sources.py --policy high_priority
"""
import argparse
import asyncio
import logging
import os
import sys
import time
from pathlib import Path
from typing import List, Optional

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from apps.api.database import AsyncSessionLocal
from services.ingestion.pipeline import IngestionPipeline
from services.sources.registry import SourceDefinition, source_registry
from shared.constants import PollingPolicy, PriorityLevel

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("signal.poller")


async def poll_single_source(pipeline: IngestionPipeline, source_def: SourceDefinition) -> dict:
    """Run ingestion for a single source definition and return audit stats."""
    if not source_def.enabled or not source_def.connector_class:
        logger.info(f"Skipping disabled or unconfigured source: {source_def.name}")
        return {
            "name": source_def.name,
            "slug": source_def.slug,
            "status": "SKIPPED",
            "duration_ms": 0,
            "opportunities": 0,
            "error": None,
        }

    connector = source_def.connector_class()
    start_t = time.perf_counter()
    try:
        # Check health first
        healthy = await connector.health_check()
        if not healthy:
            logger.warning(f"Health check reported unhealthy for {source_def.name}")

        opps = await pipeline.process_connector(connector)
        duration_ms = round((time.perf_counter() - start_t) * 1000, 2)
        return {
            "name": source_def.name,
            "slug": source_def.slug,
            "status": "SUCCESS",
            "duration_ms": duration_ms,
            "opportunities": len(opps),
            "error": None,
        }
    except Exception as exc:
        duration_ms = round((time.perf_counter() - start_t) * 1000, 2)
        logger.error(f"Error polling {source_def.name}: {exc}")
        return {
            "name": source_def.name,
            "slug": source_def.slug,
            "status": "FAILED",
            "duration_ms": duration_ms,
            "opportunities": 0,
            "error": str(exc),
        }


async def main():
    parser = argparse.ArgumentParser(description="SIGNAL Source Polling Runner")
    parser.add_argument("--source", type=str, default="all", help="Source slug to poll or 'all'")
    parser.add_argument("--priority", type=str, choices=["critical", "high", "medium", "low"], help="Filter by priority")
    parser.add_argument(
        "--policy",
        type=str,
        choices=["high_priority", "medium_priority", "low_priority", "archival"],
        help="Filter by polling policy",
    )
    args = parser.parse_args()

    # Filter target sources
    selected: List[SourceDefinition] = []
    if args.source.lower() == "all":
        selected = source_registry.list_sources(enabled=True)
    else:
        src = source_registry.get(args.source.lower())
        if not src:
            logger.error(f"Source with slug '{args.source}' not found in SourceRegistry.")
            sys.exit(1)
        selected = [src]

    if args.priority:
        target_prio = PriorityLevel(args.priority.lower())
        selected = [s for s in selected if s.priority == target_prio]

    if args.policy:
        target_policy = PollingPolicy(args.policy.lower())
        selected = [s for s in selected if s.polling_policy == target_policy]

    if not selected:
        print("No matching active sources found for the specified criteria.")
        return

    print("=" * 80)
    print(f"SIGNAL — Source Poller (Targets: {len(selected)} sources)")
    print("=" * 80)

    results = []
    async with AsyncSessionLocal() as session:
        pipeline = IngestionPipeline(session)
        for src in selected:
            print(f"--> Polling: {src.name} ({src.slug}) [{src.source_type.value}]...")
            res = await poll_single_source(pipeline, src)
            results.append(res)

    print("\n" + "=" * 80)
    print("POLLING EXECUTION SUMMARY")
    print("=" * 80)
    print(f"{'Source Name':<26} {'Status':<10} {'Duration (ms)':<15} {'Opps Saved':<12} {'Notes'}")
    print("-" * 80)
    for r in results:
        notes = f"Error: {r['error']}" if r['error'] else "OK"
        print(f"{r['name']:<26} {r['status']:<10} {r['duration_ms']:<15} {r['opportunities']:<12} {notes}")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
