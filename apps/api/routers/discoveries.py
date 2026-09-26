import math
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc

from apps.api.database import get_db
from apps.api.models.discovery import RawDiscovery
from apps.api.schemas.common import PaginatedResponse
from apps.api.schemas.discovery import RawDiscoveryRead
from shared.constants import DiscoveryStatus

router = APIRouter(prefix="/discoveries", tags=["Discoveries"])


@router.get("", response_model=PaginatedResponse[RawDiscoveryRead], status_code=status.HTTP_200_OK)
async def list_discoveries(
    db: AsyncSession = Depends(get_db),
    status_filter: Optional[DiscoveryStatus] = Query(None, alias="status", description="Filter by discovery processing status"),
    classification_filter: Optional[str] = Query(None, alias="classification", description="Filter by content classification"),
    source_id: Optional[str] = Query(None, description="Filter by originating source ID"),
    search: Optional[str] = Query(None, description="Search in raw title"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
):
    """
    List raw discoveries recorded by connectors with complete audit trail and status transitions.
    """
    stmt = select(RawDiscovery)
    count_stmt = select(func.count(RawDiscovery.id))

    if status_filter:
        stmt = stmt.where(RawDiscovery.status == status_filter.value)
        count_stmt = count_stmt.where(RawDiscovery.status == status_filter.value)

    if classification_filter:
        stmt = stmt.where(RawDiscovery.content_classification == classification_filter)
        count_stmt = count_stmt.where(RawDiscovery.content_classification == classification_filter)

    if source_id:
        stmt = stmt.where(RawDiscovery.source_id == source_id)
        count_stmt = count_stmt.where(RawDiscovery.source_id == source_id)


    if search:
        search_pattern = f"%{search}%"
        stmt = stmt.where(RawDiscovery.raw_title.ilike(search_pattern))
        count_stmt = count_stmt.where(RawDiscovery.raw_title.ilike(search_pattern))

    total = (await db.execute(count_stmt)).scalar_one()

    stmt = stmt.order_by(desc(RawDiscovery.fetched_at)).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)
    items = result.scalars().all()

    return PaginatedResponse(
        items=[RawDiscoveryRead.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total > 0 else 1,
    )



@router.get("/{discovery_id}", response_model=RawDiscoveryRead, status_code=status.HTTP_200_OK)
async def get_discovery(discovery_id: str, db: AsyncSession = Depends(get_db)):
    """
    Get full details for a specific raw discovery audit record.
    """
    stmt = select(RawDiscovery).where(RawDiscovery.id == discovery_id)
    discovery = (await db.execute(stmt)).scalars().first()
    if not discovery:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Discovery '{discovery_id}' not found")
    return RawDiscoveryRead.model_validate(discovery)
