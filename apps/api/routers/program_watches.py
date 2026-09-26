"""
FastAPI Router for Program Watches and Matches
"""
import math
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from apps.api.database import get_db
from apps.api.models.program_watch import (
    ProgramWatch,
    ProgramWatchAlias,
    ProgramWatchKeyword,
    ProgramWatchSource,
    ProgramWatchMatch,
)
from apps.api.schemas.common import PaginatedResponse
from apps.api.schemas.program_watch import (
    ProgramWatchCreate,
    ProgramWatchDetailRead,
    ProgramWatchMatchDetailRead,
    ProgramWatchRead,
    ProgramWatchUpdate,
)
from shared.constants import WatchPriority, WatchMatchLevel
from shared.utils import normalize_title

router = APIRouter(prefix="/program-watches", tags=["Program Watches"])


@router.get("", response_model=PaginatedResponse[ProgramWatchRead])
async def list_program_watches(
    db: AsyncSession = Depends(get_db),
    priority: Optional[WatchPriority] = Query(None, description="Filter by priority tier"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    organization_id: Optional[str] = Query(None, description="Filter by organization ID"),
    search: Optional[str] = Query(None, description="Search watch name or canonical name"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(20, ge=1, le=100, description="Page size (1 to 100)"),
    limit: Optional[int] = Query(None, ge=1, le=100, description="Alternative limit"),
    offset: Optional[int] = Query(None, ge=0, description="Alternative offset"),
):
    """List program watches with filtering and pagination."""
    query = select(ProgramWatch)

    if priority:
        query = query.where(ProgramWatch.priority == priority.value)
    if is_active is not None:
        query = query.where(ProgramWatch.is_active == is_active)
    if organization_id:
        query = query.where(ProgramWatch.organization_id == organization_id)
    if search and search.strip():
        search_pattern = f"%{search.strip()}%"
        query = query.where(
            (ProgramWatch.name.ilike(search_pattern)) | (ProgramWatch.canonical_name.ilike(search_pattern))
        )

    count_stmt = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    effective_limit = limit if limit is not None else page_size
    effective_offset = offset if offset is not None else (page - 1) * page_size
    effective_page = (effective_offset // effective_limit) + 1

    query = query.order_by(ProgramWatch.created_at.desc()).offset(effective_offset).limit(effective_limit)
    items = (await db.execute(query)).scalars().all()

    return PaginatedResponse(
        items=items,
        total=total,
        page=effective_page,
        page_size=effective_limit,
        pages=math.ceil(total / effective_limit) if total > 0 else 1,
    )


@router.post("", response_model=ProgramWatchDetailRead, status_code=status.HTTP_201_CREATED)
async def create_program_watch(
    data: ProgramWatchCreate,
    db: AsyncSession = Depends(get_db),
):
    """Register a new monitored ProgramWatch with optional nested aliases and keywords."""
    norm_canonical = normalize_title(data.canonical_name or data.name)

    existing = (
        await db.execute(select(ProgramWatch).where(ProgramWatch.canonical_name == norm_canonical))
    ).scalars().first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"ProgramWatch with canonical_name '{norm_canonical}' already exists (ID: {existing.id}).",
        )

    watch = ProgramWatch(
        name=data.name,
        canonical_name=norm_canonical,
        organization_id=data.organization_id,
        description=data.description,
        priority=data.priority.value,
        is_active=data.is_active,
    )
    db.add(watch)
    await db.flush()

    if data.aliases:
        for a in data.aliases:
            alias_row = ProgramWatchAlias(
                program_watch_id=watch.id,
                alias=a.alias,
                normalized_alias=normalize_title(a.alias),
            )
            db.add(alias_row)

    if data.keywords:
        for k in data.keywords:
            kw_row = ProgramWatchKeyword(
                program_watch_id=watch.id,
                keyword=k.keyword,
                normalized_keyword=normalize_title(k.keyword),
                weight=k.weight,
                is_distinctive=k.is_distinctive,
            )
            db.add(kw_row)

    if data.sources:
        for s in data.sources:
            src_row = ProgramWatchSource(
                program_watch_id=watch.id,
                source_id=s.source_id,
                url=s.url,
                priority=s.priority,
                is_active=s.is_active,
            )
            db.add(src_row)

    await db.commit()

    # Re-fetch with eager loaded relationships
    fetch_stmt = (
        select(ProgramWatch)
        .options(
            selectinload(ProgramWatch.organization),
            selectinload(ProgramWatch.aliases),
            selectinload(ProgramWatch.keywords),
            selectinload(ProgramWatch.sources),
        )
        .where(ProgramWatch.id == watch.id)
    )
    return (await db.execute(fetch_stmt)).scalars().first()


@router.get("/{id}", response_model=ProgramWatchDetailRead)
async def get_program_watch(
    id: str,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve full details of a specific ProgramWatch including aliases, keywords, and sources."""
    stmt = (
        select(ProgramWatch)
        .options(
            selectinload(ProgramWatch.organization),
            selectinload(ProgramWatch.aliases),
            selectinload(ProgramWatch.keywords),
            selectinload(ProgramWatch.sources),
        )
        .where(ProgramWatch.id == id)
    )
    watch = (await db.execute(stmt)).scalars().first()
    if not watch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"ProgramWatch with ID '{id}' not found",
        )
    return watch


@router.patch("/{id}", response_model=ProgramWatchDetailRead)
async def update_program_watch(
    id: str,
    data: ProgramWatchUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update a ProgramWatch (e.g. toggle is_active, change priority or description)."""
    stmt = (
        select(ProgramWatch)
        .options(
            selectinload(ProgramWatch.organization),
            selectinload(ProgramWatch.aliases),
            selectinload(ProgramWatch.keywords),
            selectinload(ProgramWatch.sources),
        )
        .where(ProgramWatch.id == id)
    )
    watch = (await db.execute(stmt)).scalars().first()
    if not watch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"ProgramWatch with ID '{id}' not found",
        )

    if data.name is not None:
        watch.name = data.name
    if data.canonical_name is not None:
        watch.canonical_name = normalize_title(data.canonical_name)
    if data.organization_id is not None:
        watch.organization_id = data.organization_id
    if data.description is not None:
        watch.description = data.description
    if data.priority is not None:
        watch.priority = data.priority.value
    if data.is_active is not None:
        watch.is_active = data.is_active

    await db.commit()
    return watch


@router.get("/{id}/matches", response_model=PaginatedResponse[ProgramWatchMatchDetailRead])
async def get_program_watch_matches(
    id: str,
    db: AsyncSession = Depends(get_db),
    match_level: Optional[WatchMatchLevel] = Query(None, description="Filter by match level"),
    min_score: Optional[float] = Query(None, ge=0.0, le=1.0, description="Minimum match score"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(20, ge=1, le=100, description="Page size (1 to 100)"),
    limit: Optional[int] = Query(None, ge=1, le=100, description="Alternative limit"),
    offset: Optional[int] = Query(None, ge=0, description="Alternative offset"),
):
    """Get chronological matches for a specific monitored ProgramWatch."""
    # Ensure watch exists
    watch = (await db.execute(select(ProgramWatch).where(ProgramWatch.id == id))).scalars().first()
    if not watch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"ProgramWatch with ID '{id}' not found",
        )

    query = (
        select(ProgramWatchMatch)
        .options(
            selectinload(ProgramWatchMatch.program_watch),
            selectinload(ProgramWatchMatch.raw_discovery),
        )
        .where(ProgramWatchMatch.program_watch_id == id)
    )

    if match_level:
        query = query.where(ProgramWatchMatch.match_level == match_level.value)
    if min_score is not None:
        query = query.where(ProgramWatchMatch.match_score >= min_score)

    count_stmt = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    effective_limit = limit if limit is not None else page_size
    effective_offset = offset if offset is not None else (page - 1) * page_size
    effective_page = (effective_offset // effective_limit) + 1

    query = query.order_by(ProgramWatchMatch.created_at.desc()).offset(effective_offset).limit(effective_limit)
    items = (await db.execute(query)).scalars().all()

    return PaginatedResponse(
        items=items,
        total=total,
        page=effective_page,
        page_size=effective_limit,
        pages=math.ceil(total / effective_limit) if total > 0 else 1,
    )


@router.get("/matches/all", response_model=PaginatedResponse[ProgramWatchMatchDetailRead])
async def list_all_watch_matches(
    db: AsyncSession = Depends(get_db),
    program_watch_id: Optional[str] = Query(None, description="Filter by ProgramWatch ID"),
    match_level: Optional[WatchMatchLevel] = Query(None, description="Filter by match level"),
    min_score: Optional[float] = Query(None, ge=0.0, le=1.0, description="Minimum match score"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(20, ge=1, le=100, description="Page size (1 to 100)"),
    limit: Optional[int] = Query(None, ge=1, le=100, description="Alternative limit"),
    offset: Optional[int] = Query(None, ge=0, description="Alternative offset"),
):
    """Global query endpoint for all recorded program watch matches."""
    query = select(ProgramWatchMatch).options(
        selectinload(ProgramWatchMatch.program_watch),
        selectinload(ProgramWatchMatch.raw_discovery),
    )

    if program_watch_id:
        query = query.where(ProgramWatchMatch.program_watch_id == program_watch_id)
    if match_level:
        query = query.where(ProgramWatchMatch.match_level == match_level.value)
    if min_score is not None:
        query = query.where(ProgramWatchMatch.match_score >= min_score)

    count_stmt = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    effective_limit = limit if limit is not None else page_size
    effective_offset = offset if offset is not None else (page - 1) * page_size
    effective_page = (effective_offset // effective_limit) + 1

    query = query.order_by(ProgramWatchMatch.created_at.desc()).offset(effective_offset).limit(effective_limit)
    items = (await db.execute(query)).scalars().all()

    return PaginatedResponse(
        items=items,
        total=total,
        page=effective_page,
        page_size=effective_limit,
        pages=math.ceil(total / effective_limit) if total > 0 else 1,
    )
