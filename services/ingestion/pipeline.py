"""
Ingestion Pipeline Coordinator — Executes discovery, filtering, classification, and lifecycle processing
"""
import logging
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from apps.api.models.discovery import RawDiscovery
from apps.api.models.opportunity import Opportunity
from apps.api.models.source import Source
from connectors.base_connector import BaseConnector, RawItem
from services.ingestion.deduplication import Deduplicator
from services.ingestion.filter import fast_filter
from services.intelligence.classifier import DomainClassifier
from services.lifecycle.engine import LifecycleEngine
from services.watch.engine import ProgramWatchEngine
from shared.constants import DiscoveryStatus
from shared.utils import compute_content_hash, canonicalize_url, slugify

import time
from services.ingestion.change_detection import SnapshotManager
from shared.constants import DiscoveryStatus, SourceHealthStatus

logger = logging.getLogger("signal.ingestion")


class IngestionPipeline:
    """Coordinates the deterministic filter -> classification -> watch engine -> entity resolution -> lifecycle pipeline."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.deduplicator = Deduplicator(db)
        self.lifecycle_engine = LifecycleEngine(db)
        self.watch_engine = ProgramWatchEngine(db)
        self.snapshot_manager = SnapshotManager(db)

    async def get_or_create_source(self, connector: BaseConnector) -> Source:
        """Find or automatically register a Source record for the given connector."""
        slug = slugify(connector.name)
        stmt = select(Source).where(Source.slug == slug)
        source = (await self.db.execute(stmt)).scalars().first()
        if not source:
            source = Source(
                name=connector.name,
                slug=slug,
                category=connector.category.value,
                source_type=connector.source_type.value,
                base_url=connector.base_url or "https://signal.internal",
                trust_level=connector.trust_level.value,
                is_active=connector.is_active,
                status=SourceHealthStatus.HEALTHY.value,
            )
            self.db.add(source)
            await self.db.flush()
        return source

    async def process_connector(self, connector: BaseConnector) -> List[Opportunity]:
        """Poll connector, record discoveries, snapshots, health, and process candidate items."""
        if not connector.is_active:
            logger.info(f"[Ingestion] Skipping inactive connector: {connector.name}")
            return []

        logger.info(f"[Ingestion] Starting ingestion for connector: {connector.name}")
        now = datetime.now(timezone.utc)
        start_time = time.perf_counter()

        # Ensure Source record exists
        source_record = await self.get_or_create_source(connector)
        source_record.last_polled_at = now
        await self.db.flush()

        try:
            raw_items = await connector.fetch_raw_items()
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

            # Update rolling average response time
            if source_record.average_response_time is None:
                source_record.average_response_time = duration_ms
            else:
                source_record.average_response_time = round(
                    (source_record.average_response_time * 0.7) + (duration_ms * 0.3), 2
                )

            # Record point-in-time snapshot and detect changes
            combined_text = "\n---\n".join([f"{i.title}\n{i.content}" for i in raw_items])
            snapshot, evaluation = await self.snapshot_manager.record_snapshot(
                source_id=source_record.id,
                raw_content=combined_text,
                items_count=len(raw_items),
                metadata={"fetch_duration_ms": duration_ms, "connector_name": slugify(connector.name)},
            )
            logger.info(
                f"[Ingestion] Recorded snapshot {snapshot.id[:8]} for {connector.name}: "
                f"change_type={evaluation.change_type.value}, is_meaningful={evaluation.is_meaningful}"
            )

            saved_opportunities: List[Opportunity] = []
            seen_opp_ids = set()

            for item in raw_items:
                try:
                    # Enrich item metadata
                    if not item.metadata:
                        item.metadata = {}
                    item.metadata.setdefault("connector_name", slugify(connector.name))
                    item.metadata.setdefault("source_type", connector.source_type.value)
                    item.metadata.setdefault("fetch_duration_ms", duration_ms)
                    item.metadata.setdefault("parser_version", "1.0")

                    opp = await self.process_raw_item(
                        item,
                        source_record=source_record,
                        source_trust=connector.trust_level.value,
                    )
                    if opp and opp.id not in seen_opp_ids:
                        saved_opportunities.append(opp)
                        seen_opp_ids.add(opp.id)
                except Exception as item_exc:
                    logger.error(f"[Ingestion] Error processing item '{item.title}': {item_exc}", exc_info=True)

            source_record.last_successful_check = now
            source_record.consecutive_failures = 0
            source_record.status = SourceHealthStatus.HEALTHY.value
            source_record.last_error = None
            await self.db.commit()
            logger.info(
                f"[Ingestion] Successfully completed connector '{connector.name}' in {duration_ms}ms: "
                f"{len(saved_opportunities)} opportunities processed from {len(raw_items)} discoveries"
            )
            return saved_opportunities
        except Exception as exc:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            logger.error(f"[Ingestion] Connector '{connector.name}' run failed in {duration_ms}ms: {exc}", exc_info=True)
            source_record.failure_count = (source_record.failure_count or 0) + 1
            source_record.consecutive_failures = (source_record.consecutive_failures or 0) + 1
            source_record.last_error = str(exc)

            if source_record.consecutive_failures >= 5:
                source_record.status = SourceHealthStatus.FAILING.value
            elif source_record.consecutive_failures >= 3:
                source_record.status = SourceHealthStatus.DEGRADED.value
            else:
                source_record.status = SourceHealthStatus.HEALTHY.value

            await self.db.commit()
            raise

    async def ingest_raw_item(
        self,
        item: RawItem,
        source_id: Optional[str] = None,
        source_record: Optional[Source] = None,
    ) -> RawDiscovery:
        """Create and audit log a RawDiscovery record idempotently without running downstream engines."""
        canonical_item_url = item.canonical_url() if hasattr(item, "canonical_url") else canonicalize_url(item.url)
        content_hash = compute_content_hash(item.content)
        now = datetime.now(timezone.utc)
        resolved_source_id = source_id or (source_record.id if source_record else None)

        disc_stmt = select(RawDiscovery).where(
            RawDiscovery.content_hash == content_hash,
            RawDiscovery.canonical_url == canonical_item_url,
        )
        existing_disc = (await self.db.execute(disc_stmt)).scalars().first()
        if existing_disc:
            return existing_disc

        discovery = RawDiscovery(
            source_id=resolved_source_id,
            external_id=item.source_identifier,
            original_url=item.url,
            canonical_url=canonical_item_url,
            raw_title=item.title,
            raw_content=item.content,
            published_at=item.published_at,
            fetched_at=now,
            content_hash=content_hash,
            status=DiscoveryStatus.DISCOVERED.value,
            connector_metadata=item.metadata,
        )
        self.db.add(discovery)
        try:
            await self.db.flush()
        except IntegrityError:
            await self.db.rollback()
            existing_disc = (await self.db.execute(disc_stmt)).scalars().first()
            if existing_disc:
                return existing_disc
            raise
        return discovery

    async def process_raw_item(
        self,
        item: RawItem,
        source_record: Optional[Source] = None,
        source_trust: str = "high",
    ) -> Optional[Opportunity]:
        """Process a single raw item through discovery audit, filtering, classification, and lifecycle engine."""
        canonical_item_url = item.canonical_url() if hasattr(item, "canonical_url") else canonicalize_url(item.url)
        content_hash = compute_content_hash(item.content)
        source_id = source_record.id if source_record else None

        # 1. Audit Logging: Check if discovery already recorded
        disc_stmt = select(RawDiscovery).where(
            RawDiscovery.content_hash == content_hash,
            RawDiscovery.canonical_url == canonical_item_url,
        )
        existing_disc = (await self.db.execute(disc_stmt)).scalars().first()
        if existing_disc:
            logger.info(f"[Ingestion] RawDiscovery already exists for '{item.title}' (ID: {existing_disc.id})")
            if existing_disc.opportunity_id:
                opp = (
                    await self.db.execute(
                        select(Opportunity).where(Opportunity.id == existing_disc.opportunity_id)
                    )
                ).scalars().first()
                if opp:
                    return opp
            return None

        discovery = await self.ingest_raw_item(item, source_record=source_record)

        # 2. Content Understanding & Domain Classification
        understanding = DomainClassifier.classify(
            raw_title=item.title,
            raw_content=item.content,
            connector_metadata=item.metadata,
            source_category=source_record.category if source_record else None,
            source_name=source_record.name if source_record else None,
        )

        # 3. Program Watch Engine Evaluation ⭐ (Non-blocking monitored program matcher)
        try:
            await self.watch_engine.evaluate_discovery(discovery)
        except Exception as e:
            logger.warning(f"[Ingestion] ProgramWatchEngine failed for discovery '{discovery.id}': {e}", exc_info=True)

        # 4. Informational / Non-actionable policy bypass
        if not understanding.is_actionable_opportunity:
            return await self.lifecycle_engine.process_discovery_lifecycle(
                discovery=discovery,
                understanding=understanding,
                source_id=source_id,
                source_category=source_record.category if source_record else None,
                source_trust=source_trust,
            )

        # 5. Fast Filtering (Deterministic pre-filter for opportunity candidates)
        is_candidate, matches, score = fast_filter.evaluate(item.title, item.content)
        if not is_candidate:
            discovery.content_classification = understanding.classification.value
            discovery.status = DiscoveryStatus.FILTERED_OUT.value
            discovery.processing_reason = f"Fast filter score below threshold ({score:.2f})"
            await self.db.flush()
            logger.debug(f"[Ingestion] Filtered out item: '{item.title}'")
            return None

        # 5. Lifecycle Engine Execution (handles entity resolution, alias maintenance, and idempotent event logging)
        return await self.lifecycle_engine.process_discovery_lifecycle(
            discovery=discovery,
            understanding=understanding,
            source_id=source_id,
            source_category=source_record.category if source_record else None,
            source_trust=source_trust,
        )
