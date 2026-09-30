"""
Scheduler Observability & Ingestion Control API Router (Phase 5A)
Exposes scheduler health metrics, ScheduledJob audit history, and on-demand source polling controls.
"""
from datetime import datetime, timedelta, timezone
import logging
import math
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from apps.api.core.auth import get_current_active_user
from apps.api.database import get_db
from apps.api.models.scheduled_job import ScheduledJob
from apps.api.models.source import Source
from apps.api.models.user import User
from apps.api.schemas.common import PaginatedResponse
from apps.api.schemas.scheduler import (
    PollAllTriggerResponse,
    PollTriggerResponse,
    ScheduledJobRead,
    SchedulerSourcesStatus,
    SchedulerStatusResponse,
)
from services.scheduler.scheduler import get_scheduler, poll_source
from shared.constants import PollingPolicy, ScheduledJobStatus

logger = logging.getLogger("signal.api.scheduler")
router = APIRouter(prefix="/scheduler", tags=["Scheduler Observability"])


@router.get("/status", response_model=SchedulerStatusResponse, status_code=status.HTTP_200_OK)
async def get_scheduler_status(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Return scheduler operational health, active APScheduler jobs,
    configured source counts, and 24-hour job outcome counts.
    """
    scheduler = get_scheduler(request.app)
    running = getattr(scheduler, "running", False)
    tz_str = str(getattr(scheduler, "timezone", "UTC"))

    try:
        active_jobs = [j.id for j in scheduler.get_jobs()]
    except Exception:
        active_jobs = []

    # 1. Source counts
    total_sources = (await db.execute(select(func.count(Source.id)))).scalar() or 0
    active_sources = (
        await db.execute(select(func.count(Source.id)).where(Source.is_active == True))
    ).scalar() or 0
    enabled_sources = (
        await db.execute(
            select(func.count(Source.id)).where(
                and_(Source.is_active == True, Source.scheduler_enabled == True)
            )
        )
    ).scalar() or 0

    # 2. Due for polling evaluation
    now = datetime.now(timezone.utc)
    enabled_stmt = select(Source).where(
        and_(Source.is_active == True, Source.scheduler_enabled == True)
    )
    sources = (await db.execute(enabled_stmt)).scalars().all()

    due_count = 0
    for src in sources:
        base_interval = src.monitor_frequency_minutes or 60
        policy = src.polling_policy

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
                multiplier = min(16, 2 ** (src.consecutive_failures - 3))
                interval = min(1440, base_interval * multiplier)
        else:
            interval = base_interval

        if src.last_polled_at is None:
            due_count += 1
        else:
            last_polled = src.last_polled_at
            if last_polled.tzinfo is None:
                last_polled = last_polled.replace(tzinfo=timezone.utc)
            if (now - last_polled).total_seconds() / 60 >= interval:
                due_count += 1

    # 3. 24-hour job metrics
    since_24h = now - timedelta(hours=24)
    recent_success_stmt = select(func.count(ScheduledJob.id)).where(
        ScheduledJob.status == ScheduledJobStatus.SUCCESS.value,
        ScheduledJob.started_at >= since_24h,
    )
    recent_success = (await db.execute(recent_success_stmt)).scalar() or 0

    recent_fail_stmt = select(func.count(ScheduledJob.id)).where(
        ScheduledJob.status == ScheduledJobStatus.FAILURE.value,
        ScheduledJob.started_at >= since_24h,
    )
    recent_fail = (await db.execute(recent_fail_stmt)).scalar() or 0

    return SchedulerStatusResponse(
        running=running,
        timezone=tz_str,
        scheduler_jobs_count=len(active_jobs),
        active_jobs=active_jobs,
        sources=SchedulerSourcesStatus(
            total=total_sources,
            active=active_sources,
            scheduler_enabled=enabled_sources,
            due_for_polling=due_count,
        ),
        recent_successful_polls_24h=recent_success,
        recent_failed_polls_24h=recent_fail,
    )


@router.get("/jobs", response_model=PaginatedResponse[ScheduledJobRead], status_code=status.HTTP_200_OK)
async def list_scheduled_jobs(
    db: AsyncSession = Depends(get_db),
    source_slug: Optional[str] = Query(None, description="Filter by source slug"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by job status"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
):
    """
    Return paginated ScheduledJob audit records with newest executions first.
    """
    query = select(ScheduledJob).options(selectinload(ScheduledJob.source))

    if source_slug:
        query = query.join(Source).where(Source.slug == source_slug)
    if status_filter:
        query = query.where(ScheduledJob.status == status_filter)

    count_stmt = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    query = (
        query.order_by(desc(ScheduledJob.started_at), desc(ScheduledJob.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    jobs = (await db.execute(query)).scalars().all()

    items: List[ScheduledJobRead] = []
    for job in jobs:
        items.append(
            ScheduledJobRead(
                id=job.id,
                source_id=job.source_id,
                source_slug=job.source.slug if job.source else None,
                source_name=job.source.name if job.source else None,
                status=job.status,
                started_at=job.started_at,
                finished_at=job.finished_at,
                duration_ms=job.duration_ms,
                items_discovered=job.items_discovered,
                items_processed=job.items_processed,
                error_message=job.error_message,
                created_at=job.created_at,
            )
        )

    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total > 0 else 1,
    )


@router.post("/poll/{source_slug}", response_model=PollTriggerResponse, status_code=status.HTTP_200_OK)
async def trigger_source_poll(
    source_slug: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Trigger an on-demand poll for a registered source by slug.
    Reuses the existing poll_source pipeline and creates a ScheduledJob audit record.
    """
    stmt = select(Source).where(Source.slug == source_slug)
    source = (await db.execute(stmt)).scalars().first()

    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source with slug '{source_slug}' not found.",
        )

    await poll_source(source_slug, db)

    # Fetch the audit record created by poll_source
    job_stmt = (
        select(ScheduledJob)
        .where(ScheduledJob.source_id == source.id)
        .order_by(desc(ScheduledJob.started_at), desc(ScheduledJob.created_at))
        .limit(1)
    )
    latest_job = (await db.execute(job_stmt)).scalars().first()

    return PollTriggerResponse(
        success=(latest_job.status == ScheduledJobStatus.SUCCESS.value) if latest_job else False,
        source_slug=source.slug,
        source_name=source.name,
        job_id=latest_job.id if latest_job else None,
        status=latest_job.status if latest_job else "unknown",
        items_discovered=latest_job.items_discovered if latest_job else 0,
        items_processed=latest_job.items_processed if latest_job else 0,
        duration_ms=latest_job.duration_ms if latest_job else None,
        error_message=latest_job.error_message if latest_job else None,
    )


@router.post("/poll-all", response_model=PollAllTriggerResponse, status_code=status.HTTP_200_OK)
async def trigger_poll_all_eligible_sources(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Trigger polling for all active, scheduler-enabled sources.
    Reuses the existing poll_source pipeline for each source.
    """
    stmt = select(Source).where(and_(Source.is_active == True, Source.scheduler_enabled == True))
    eligible_sources = (await db.execute(stmt)).scalars().all()

    triggered_slugs: List[str] = []
    for src in eligible_sources:
        try:
            await poll_source(src.slug, db)
            triggered_slugs.append(src.slug)
        except Exception as poll_exc:
            logger.error("Error polling source %s in poll-all: %s", src.slug, poll_exc)
            triggered_slugs.append(f"{src.slug} (failed: {poll_exc})")

    return PollAllTriggerResponse(
        success=True,
        total_eligible=len(eligible_sources),
        triggered_sources=triggered_slugs,
        message=f"Triggered polling for {len(triggered_slugs)} eligible sources.",
    )
