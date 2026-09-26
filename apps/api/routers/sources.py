"""
Sources API Router — Extended with health tracking, snapshots, and slug resolution
"""
import math
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import desc, func, select

from apps.api.database import get_db
from apps.api.models.source import Source
from apps.api.models.snapshot import SourceSnapshot
from apps.api.schemas.common import PaginatedResponse
from apps.api.schemas.source import SourceCreate, SourceHealthRead, SourceRead, SourceUpdate
from apps.api.schemas.snapshot import SourceSnapshotRead
from shared.constants import OpportunityCategory
from shared.utils import slugify

router = APIRouter(prefix="/sources", tags=["Sources"])


@router.get("", response_model=PaginatedResponse[SourceRead])
async def list_sources(
    db: AsyncSession = Depends(get_db),
    category: Optional[OpportunityCategory] = Query(None),
    status: Optional[str] = Query(None),
    priority_level: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """List monitored sources with category, status, priority, and active filters."""
    query = select(Source)
    if category:
        query = query.where(Source.category == category.value)
    if status:
        query = query.where(Source.status == status)
    if priority_level:
        query = query.where(Source.priority_level == priority_level)
    if is_active is not None:
        query = query.where(Source.is_active == is_active)

    count_stmt = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    query = query.order_by(Source.priority.asc(), Source.name.asc()).offset((page - 1) * page_size).limit(page_size)
    items = (await db.execute(query)).scalars().all()

    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total > 0 else 1,
    )


@router.post("", response_model=SourceRead, status_code=status.HTTP_201_CREATED)
async def create_source(
    data: SourceCreate,
    db: AsyncSession = Depends(get_db),
):
    """Register a new source to monitor."""
    slug = data.slug or slugify(data.name)
    existing = (await db.execute(select(Source).where(Source.slug == slug))).scalars().first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Source with slug '{slug}' already exists.",
        )

    source = Source(
        name=data.name,
        slug=slug,
        organization_id=data.organization_id,
        category=data.category.value,
        source_type=data.source_type.value,
        base_url=data.base_url,
        api_endpoint=data.api_endpoint,
        monitor_frequency_minutes=data.monitor_frequency_minutes,
        priority=data.priority,
        trust_level=data.trust_level.value,
        is_active=data.is_active,
        notes=data.notes,
    )
    db.add(source)
    await db.commit()
    await db.refresh(source)
    return source


@router.get("/{identifier}", response_model=SourceRead)
async def get_source(
    identifier: str,
    db: AsyncSession = Depends(get_db),
):
    """Get source configuration by ID or slug."""
    source = (
        await db.execute(
            select(Source).where((Source.id == identifier) | (Source.slug == identifier))
        )
    ).scalars().first()
    if not source:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")
    return source


@router.get("/{identifier}/health", response_model=SourceHealthRead)
async def get_source_health(
    identifier: str,
    db: AsyncSession = Depends(get_db),
):
    """Get health status, response timings, and error history for a source."""
    source = (
        await db.execute(
            select(Source).where((Source.id == identifier) | (Source.slug == identifier))
        )
    ).scalars().first()
    if not source:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")

    return SourceHealthRead(
        slug=source.slug,
        name=source.name,
        status=source.status,
        failure_count=source.failure_count,
        consecutive_failures=source.consecutive_failures,
        average_response_time_ms=source.average_response_time,
        last_polled_at=source.last_polled_at,
        last_successful_check=source.last_successful_check,
        last_error=source.last_error,
        polling_policy=source.polling_policy,
        priority_level=source.priority_level,
    )


@router.get("/{identifier}/snapshots", response_model=PaginatedResponse[SourceSnapshotRead])
async def get_source_snapshots(
    identifier: str,
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """Get historical content snapshots for a source."""
    source = (
        await db.execute(
            select(Source).where((Source.id == identifier) | (Source.slug == identifier))
        )
    ).scalars().first()
    if not source:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")

    query = (
        select(SourceSnapshot)
        .where(SourceSnapshot.source_id == source.id)
        .order_by(desc(SourceSnapshot.fetched_at))
    )

    count_stmt = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    items = (await db.execute(query.offset((page - 1) * page_size).limit(page_size))).scalars().all()

    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total > 0 else 1,
    )
