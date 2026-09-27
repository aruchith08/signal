import math
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from apps.api.database import get_db
from apps.api.models.opportunity import Opportunity
from apps.api.models.event import OpportunityEvent
from apps.api.schemas.common import PaginatedResponse
from apps.api.schemas.event import EventRead
from apps.api.schemas.opportunity import (
    OpportunityCreate,
    OpportunityDetailRead,
    OpportunityRead,
    OpportunityUpdate,
)
from shared.constants import OpportunityCategory, OpportunityStatus, VerificationStatus
from shared.utils import compute_content_hash, canonicalize_url, slugify

router = APIRouter(prefix="/opportunities", tags=["Opportunities"])



import time

_OPPORTUNITIES_CACHE: dict = {}
_OPPORTUNITIES_CACHE_TTL = 30  # 30 seconds cache


@router.get("", response_model=PaginatedResponse[OpportunityRead])
async def list_opportunities(
    db: AsyncSession = Depends(get_db),
    category: Optional[str] = Query(None, description="Filter by opportunity category"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status"),
    verification_status: Optional[str] = Query(None, description="Filter by verification tier"),
    official: Optional[bool] = Query(None, description="Filter by official publisher status"),
    current_state: Optional[str] = Query(None, description="Filter by current lifecycle state"),
    year: Optional[int] = Query(None, description="Filter by opportunity year"),
    search: Optional[str] = Query(None, description="Search keyword in title or summary"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(20, ge=1, le=100, description="Page size (1 to 100)"),
    limit: Optional[int] = Query(None, ge=1, le=100, description="Alternative limit"),
    offset: Optional[int] = Query(None, ge=0, description="Alternative offset"),
):
    """List opportunities with rich multi-criteria filtering, search, and dual pagination (page/page_size or limit/offset)."""
    cache_key = f"{category}:{status_filter}:{verification_status}:{official}:{current_state}:{year}:{search}:{page}:{page_size}:{limit}:{offset}"
    now_ts = time.time()
    if cache_key in _OPPORTUNITIES_CACHE:
        cached_time, cached_val = _OPPORTUNITIES_CACHE[cache_key]
        if now_ts - cached_time < _OPPORTUNITIES_CACHE_TTL:
            return cached_val

    query = select(Opportunity)

    if category and category.strip():
        cat_lower = category.strip().lower()
        query = query.where(func.lower(Opportunity.category) == cat_lower)
    if status_filter and status_filter.strip():
        stat_lower = status_filter.strip().lower()
        query = query.where(func.lower(Opportunity.status) == stat_lower)
    if verification_status and verification_status.strip():
        vstat_lower = verification_status.strip().lower()
        query = query.where(func.lower(Opportunity.verification_status) == vstat_lower)
    if official is not None:
        query = query.where(Opportunity.official == official)
    if current_state:
        query = query.where(Opportunity.current_state == current_state)
    if year:
        query = query.where(Opportunity.year == year)

    if search and search.strip():
        search_pattern = f"%{search.strip()}%"
        query = query.where(
            (Opportunity.title.ilike(search_pattern)) | (Opportunity.summary.ilike(search_pattern))
        )

    count_stmt = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    effective_limit = limit if limit is not None else page_size
    effective_offset = offset if offset is not None else (page - 1) * page_size
    effective_page = (effective_offset // effective_limit) + 1

    query = query.order_by(Opportunity.created_at.desc()).offset(effective_offset).limit(effective_limit)
    items = (await db.execute(query)).scalars().all()

    result = PaginatedResponse(
        items=items,
        total=total,
        page=effective_page,
        page_size=effective_limit,
        pages=math.ceil(total / effective_limit) if total > 0 else 1,
    )
    _OPPORTUNITIES_CACHE[cache_key] = (now_ts, result)
    return result


@router.post("", response_model=OpportunityDetailRead, status_code=status.HTTP_201_CREATED)
async def create_opportunity(
    data: OpportunityCreate,
    db: AsyncSession = Depends(get_db),
):
    """Manually register or inject an opportunity with attached events (for testing or curated entry)."""
    content = data.raw_content or data.title
    content_hash = compute_content_hash(content)

    # Check for existing hash
    existing = (
        await db.execute(select(Opportunity).where(Opportunity.content_hash == content_hash))
    ).scalars().first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Opportunity with identical content already exists (ID: {existing.id}).",
        )

    slug = data.slug or f"{slugify(data.title)}-{content_hash[:8]}"

    category_val = data.category.value if hasattr(data.category, "value") else str(data.category)
    status_val = data.status.value if hasattr(data.status, "value") else str(data.status)
    verification_status_val = (
        data.verification_status.value
        if hasattr(data.verification_status, "value")
        else str(data.verification_status)
    )

    opp = Opportunity(
        title=data.title,
        slug=slug,
        organization_id=data.organization_id,
        source_id=data.source_id,
        category=category_val,
        event_type=data.event_type,
        status=status_val,
        verification_status=verification_status_val,
        confidence_score=data.confidence_score,
        official=data.official,
        eligibility=data.eligibility,
        target_audience=data.target_audience,
        application_url=canonicalize_url(data.application_url) if data.application_url else None,
        raw_content=data.raw_content,
        summary=data.summary,
        content_hash=content_hash,
    )
    db.add(opp)
    await db.flush()

    if data.events:
        for evt in data.events:
            event = OpportunityEvent(
                opportunity_id=opp.id,
                event_type=evt.event_type.value,
                title=evt.title,
                description=evt.description,
                event_date=evt.event_date,
                deadline_date=evt.deadline_date,
                is_critical=evt.is_critical,
            )
            db.add(event)

    await db.commit()

    # Re-fetch with relationships loaded
    stmt = (
        select(Opportunity)
        .options(
            selectinload(Opportunity.organization),
            selectinload(Opportunity.source),
            selectinload(Opportunity.events),
            selectinload(Opportunity.aliases),
        )
        .where(Opportunity.id == opp.id)
    )
    loaded_opp = (await db.execute(stmt)).scalars().first()
    return loaded_opp


@router.get("/{id}", response_model=OpportunityDetailRead)
async def get_opportunity(
    id: str,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve full details for an opportunity, including lifecycle events, source, and organization."""
    stmt = (
        select(Opportunity)
        .options(
            selectinload(Opportunity.organization),
            selectinload(Opportunity.source),
            selectinload(Opportunity.events),
            selectinload(Opportunity.aliases),
        )
        .where(Opportunity.id == id)
    )
    opp = (await db.execute(stmt)).scalars().first()
    if not opp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Opportunity not found",
        )
    return opp


@router.get("/{id}/events", response_model=List[EventRead], status_code=status.HTTP_200_OK)
async def get_opportunity_events(
    id: str,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve complete chronological lifecycle event history for a specific opportunity."""
    opp_stmt = select(Opportunity).where(Opportunity.id == id)
    opp = (await db.execute(opp_stmt)).scalars().first()
    if not opp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Opportunity '{id}' not found",
        )

    stmt = (
        select(OpportunityEvent)
        .where(OpportunityEvent.opportunity_id == id)
        .order_by(OpportunityEvent.created_at.asc())
    )
    events = (await db.execute(stmt)).scalars().all()
    return [EventRead.model_validate(e) for e in events]

