'''Scheduler service implementation for SIGNAL platform'''

import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.database import AsyncSessionLocal
from apps.api.models.source import Source
from apps.api.models.scheduled_job import ScheduledJob
from services.ingestion.pipeline import IngestionPipeline
from services.scheduler.lock import DistributedLockManager
from shared.constants import PollingPolicy, ScheduledJobStatus, UserNotificationStatus, NotificationStatus, PriorityLevel

logger = logging.getLogger(__name__)

CONNECTOR_REGISTRY: dict = {}


def get_connector(slug: str):
    global CONNECTOR_REGISTRY
    if not CONNECTOR_REGISTRY:
        from apps.api.routers.ingestion import CONNECTOR_REGISTRY as _REG
        CONNECTOR_REGISTRY.update(_REG)
    return CONNECTOR_REGISTRY.get(slug)


def get_scheduler(app: FastAPI) -> AsyncIOScheduler:
    """Retrieve or create the singleton AsyncIOScheduler attached to the app state."""
    if not hasattr(app.state, "scheduler"):
        scheduler = AsyncIOScheduler()
        app.state.scheduler = scheduler
    return app.state.scheduler

async def poll_source(source_slug: str, db: AsyncSession) -> None:
    """Run the ingestion pipeline for a single source with distributed lock protection.

    A ``ScheduledJob`` record is created to audit the run. On success the source
    timestamps are updated; on failure the error is logged and failure counters
    are incremented.
    """
    lock_mgr = DistributedLockManager(db)
    lock_name = f"poll_source_{source_slug}"
    acquired = await lock_mgr.acquire(lock_name, timeout_seconds=300)
    if not acquired:
        logger.info(f"[Scheduler] Source '{source_slug}' is currently locked by another worker. Skipping concurrent poll.")
        return

    try:
        connector_cls = get_connector(source_slug)
        if connector_cls is None:
            logger.error("No connector registered for source slug %s", source_slug)
            return

        # Resolve source id
        result = await db.execute(select(Source.id).where(Source.slug == source_slug))
        source_id = result.scalar_one_or_none()
        if not source_id:
            from services.sources.registry import ensure_source
            src = await ensure_source(source_slug, db)
            if src:
                source_id = src.id
            else:
                logger.error("Source %s not found in DB", source_slug)
                return

        job = ScheduledJob(
            source_id=source_id,
            started_at=datetime.now(timezone.utc),
            status=ScheduledJobStatus.PENDING.value,
            items_discovered=0,
            items_processed=0,
        )
        db.add(job)
        await db.flush()  # assign job.id

        try:
            pipeline = IngestionPipeline(db)
            connector = connector_cls()
            created = await pipeline.process_connector(connector)
            job.items_discovered = len(created)
            job.items_processed = len(created)
            job.status = ScheduledJobStatus.SUCCESS.value

            # Update source metadata
            src_res = await db.execute(select(Source).where(Source.slug == source_slug))
            src: Optional[Source] = src_res.scalar_one_or_none()
            if src:
                now_utc = datetime.now(timezone.utc)
                src.last_polled_at = now_utc
                src.last_successful_check = now_utc
                src.consecutive_failures = 0
                src.failure_count = 0
        except Exception as exc:
            logger.exception("Error polling source %s", source_slug)
            job.status = ScheduledJobStatus.FAILURE.value
            job.error_message = str(exc)
            # Update failure counters on source
            src_res = await db.execute(select(Source).where(Source.slug == source_slug))
            src: Optional[Source] = src_res.scalar_one_or_none()
            if src:
                src.consecutive_failures += 1
                src.failure_count += 1
                src.last_error = str(exc)
        finally:
            job.finished_at = datetime.now(timezone.utc)
            # Ensure timezone awareness for duration calculation
            s_at = job.started_at.replace(tzinfo=timezone.utc) if job.started_at.tzinfo is None else job.started_at
            f_at = job.finished_at.replace(tzinfo=timezone.utc) if job.finished_at.tzinfo is None else job.finished_at
            job.duration_ms = int((f_at - s_at).total_seconds() * 1000)
            await db.commit()
    finally:
        await lock_mgr.release(lock_name)

async def coordinator_job(app: FastAPI) -> None:
    """Coordinator runs periodically to discover due sources and trigger polling.

    Protected by distributed lock to prevent multiple worker instances from running concurrently.
    """
    async with AsyncSessionLocal() as lock_db:
        lock_mgr = DistributedLockManager(lock_db)
        acquired = await lock_mgr.acquire("scheduler_coordinator", timeout_seconds=240)
        if not acquired:
            logger.info("[Scheduler] Coordinator is currently locked by another worker instance. Skipping concurrent run.")
            return

    try:
        async with AsyncSessionLocal() as db:
            stmt = select(Source).where(and_(Source.is_active == True, Source.scheduler_enabled == True))
            result = await db.execute(stmt)
            sources: List[Source] = result.scalars().all()

            now = datetime.now(timezone.utc)
            due_slugs: List[str] = []
            for src in sources:
                base_interval = src.monitor_frequency_minutes or 60
                policy = src.polling_policy

                # Determine effective interval based on policy enum
                if policy == PollingPolicy.HIGH_PRIORITY.value:
                    interval = 30
                elif policy == PollingPolicy.MEDIUM_PRIORITY.value:
                    interval = 120
                elif policy == PollingPolicy.LOW_PRIORITY.value:
                    interval = 360
                elif policy == PollingPolicy.ARCHIVAL.value:
                    interval = 1440
                elif policy == PollingPolicy.ADAPTIVE.value:
                    interval = base_interval
                    if src.consecutive_failures > 3:
                        # Exponential backoff capped at 24 hours
                        multiplier = min(16, 2 ** (src.consecutive_failures - 3))
                        interval = min(1440, base_interval * multiplier)
                else:
                    interval = base_interval

                if src.last_polled_at is None:
                    due = True
                else:
                    last_p = src.last_polled_at.replace(tzinfo=timezone.utc) if src.last_polled_at.tzinfo is None else src.last_polled_at
                    due = (now - last_p).total_seconds() / 60 >= interval

                if due:
                    due_slugs.append(src.slug)

        for slug in due_slugs:
            logger.info("Triggering scheduled poll for source slug=%s", slug)
            async with AsyncSessionLocal() as poll_db:
                try:
                    await poll_source(slug, poll_db)
                except Exception as poll_err:
                    logger.error("Failed polling source %s: %s", slug, poll_err)
    finally:
        async with AsyncSessionLocal() as release_db:
            await DistributedLockManager(release_db).release("scheduler_coordinator")


async def notification_retry_coordinator(app: FastAPI) -> None:
    """Periodically scans for failed NotificationDelivery records and attempts retry with backoff.
    Protected by distributed lock to prevent duplicate retry executions.
    """
    async with AsyncSessionLocal() as lock_db:
        lock_mgr = DistributedLockManager(lock_db)
        acquired = await lock_mgr.acquire("notification_retry_coordinator", timeout_seconds=240)
        if not acquired:
            logger.info("[Scheduler] Notification retry coordinator is currently locked by another worker instance. Skipping.")
            return

    try:
        logger.info("[Scheduler] Running notification retry coordinator...")
        async with AsyncSessionLocal() as session:
            try:
                from services.notifications.retry import NotificationRetryEngine
                retry_engine = NotificationRetryEngine()
                result = await retry_engine.process_retry_batch(session)
                await session.commit()
                logger.info(
                    f"[Scheduler] Notification retry coordinator finished: "
                    f"{result['eligible']} eligible, {result['succeeded']} succeeded, {result['failed']} failed"
                )
            except Exception as e:
                logger.error(f"[Scheduler] Notification retry coordinator error: {e}", exc_info=True)
    finally:
        async with AsyncSessionLocal() as release_db:
            await DistributedLockManager(release_db).release("notification_retry_coordinator")



def schedule_jobs(app: FastAPI) -> None:
    scheduler = get_scheduler(app)
    # Run source coordinator every 5 minutes
    scheduler.add_job(coordinator_job, "interval", minutes=5, args=[app], id="source_coordinator", replace_existing=True)
    # Run delivery retry coordinator every 5 minutes
    scheduler.add_job(notification_retry_coordinator, "interval", minutes=5, args=[app], id="notification_retry_coordinator", replace_existing=True)
    scheduler.start()
    logger.info("APScheduler started with source coordinator and notification retry jobs")
