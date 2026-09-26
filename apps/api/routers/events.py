"""
Opportunity Events API Router
"""
import math
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select

from apps.api.database import get_db
from apps.api.models.event import OpportunityEvent
from apps.api.models.opportunity import Opportunity
from apps.api.schemas.common import PaginatedResponse
from apps.api.schemas.event import EventCreate, EventRead
from shared.constants import EventType

router = APIRouter(prefix="/events", tags=["Events"])


@router.get("", response_model=PaginatedResponse[EventRead])
async def list_events(
    db: AsyncSession = Depends(get_db),
    opportunity_id: Optional[str] = Query(None, description="Filter by opportunity ID"),
    event_type: Optional[EventType] = Query(None, description="Filter by event type"),
    is_critical: Optional[bool] = Query(None, description="Filter for critical events"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """List opportunity lifecycle events (deadlines, contest schedules, results)."""
    query = select(OpportunityEvent)
    if opportunity_id:
        query = query.where(OpportunityEvent.opportunity_id == opportunity_id)
    if event_type:
        query = query.where(OpportunityEvent.event_type == event_type.value)
    if is_critical is not None:
        query = query.where(OpportunityEvent.is_critical == is_critical)

    count_stmt = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    query = query.order_by(OpportunityEvent.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    items = (await db.execute(query)).scalars().all()

    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total > 0 else 1,
    )


@router.post("", response_model=EventRead, status_code=status.HTTP_201_CREATED)
async def create_event(
    data: EventCreate,
    db: AsyncSession = Depends(get_db),
):
    """Attach a new event or deadline to an existing opportunity."""
    opp = (
        await db.execute(select(Opportunity).where(Opportunity.id == data.opportunity_id))
    ).scalars().first()
    if not opp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Parent opportunity '{data.opportunity_id}' not found.",
        )

    event = OpportunityEvent(
        opportunity_id=data.opportunity_id,
        event_type=data.event_type.value,
        title=data.title,
        description=data.description,
        event_date=data.event_date,
        deadline_date=data.deadline_date,
        is_critical=data.is_critical,
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)
    return event
