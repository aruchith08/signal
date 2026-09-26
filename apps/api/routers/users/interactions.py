"""
User Opportunity Interactions (Save, Follow, Bookmark) Endpoints
"""
import math
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select

from apps.api.database import get_db
from apps.api.models.user import User
from apps.api.models.opportunity import Opportunity
from apps.api.models.interaction import UserOpportunityInteraction
from apps.api.schemas.opportunity import OpportunityRead
from apps.api.schemas.common import PaginatedResponse
from apps.api.schemas.interaction import (
    UserInteractionsOverviewResponse,
    UserInteractionStatusResponse,
)
from apps.api.core.auth import get_current_user_optional
from apps.api.routers.users.common import get_user_or_404

router = APIRouter()


async def _get_or_create_interaction(user_id: str, opportunity_id: str, db: AsyncSession) -> UserOpportunityInteraction:
    stmt = select(UserOpportunityInteraction).where(
        UserOpportunityInteraction.user_id == user_id,
        UserOpportunityInteraction.opportunity_id == opportunity_id,
    )
    interaction = (await db.execute(stmt)).scalars().first()
    if not interaction:
        interaction = UserOpportunityInteraction(
            user_id=user_id,
            opportunity_id=opportunity_id,
            is_saved=False,
            is_followed=False,
        )
        db.add(interaction)
        await db.flush()
    return interaction


@router.get("/{user_id}/interactions", response_model=UserInteractionsOverviewResponse)
async def get_user_interactions(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Fetch all saved and followed opportunity IDs for the active user."""
    await get_user_or_404(user_id, db, current_user=current_user)
    stmt = select(UserOpportunityInteraction).where(UserOpportunityInteraction.user_id == user_id)
    records = (await db.execute(stmt)).scalars().all()

    saved_ids = [r.opportunity_id for r in records if r.is_saved]
    followed_ids = [r.opportunity_id for r in records if r.is_followed]
    return UserInteractionsOverviewResponse(
        saved_opportunity_ids=saved_ids,
        followed_opportunity_ids=followed_ids,
    )


@router.post("/{user_id}/opportunities/{opportunity_id}/save", response_model=UserInteractionStatusResponse)
async def save_opportunity(
    user_id: str,
    opportunity_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Bookmark / save an opportunity for personal reference."""
    await get_user_or_404(user_id, db, current_user=current_user)
    opp_stmt = select(Opportunity).where(Opportunity.id == opportunity_id)
    opp = (await db.execute(opp_stmt)).scalars().first()
    if not opp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Opportunity not found")

    interaction = await _get_or_create_interaction(user_id, opportunity_id, db)
    interaction.is_saved = True
    await db.commit()
    await db.refresh(interaction)
    return UserInteractionStatusResponse(
        opportunity_id=opportunity_id,
        is_saved=interaction.is_saved,
        is_followed=interaction.is_followed,
        notes=interaction.notes,
    )


@router.delete("/{user_id}/opportunities/{opportunity_id}/save", response_model=UserInteractionStatusResponse)
async def unsave_opportunity(
    user_id: str,
    opportunity_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Remove an opportunity from saved bookmarks."""
    await get_user_or_404(user_id, db, current_user=current_user)
    interaction = await _get_or_create_interaction(user_id, opportunity_id, db)
    interaction.is_saved = False
    await db.commit()
    await db.refresh(interaction)
    return UserInteractionStatusResponse(
        opportunity_id=opportunity_id,
        is_saved=interaction.is_saved,
        is_followed=interaction.is_followed,
        notes=interaction.notes,
    )


@router.post("/{user_id}/opportunities/{opportunity_id}/follow", response_model=UserInteractionStatusResponse)
async def follow_opportunity(
    user_id: str,
    opportunity_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Follow an opportunity to receive future lifecycle and deadline alerts."""
    await get_user_or_404(user_id, db, current_user=current_user)
    opp_stmt = select(Opportunity).where(Opportunity.id == opportunity_id)
    opp = (await db.execute(opp_stmt)).scalars().first()
    if not opp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Opportunity not found")

    interaction = await _get_or_create_interaction(user_id, opportunity_id, db)
    interaction.is_followed = True
    await db.commit()
    await db.refresh(interaction)
    return UserInteractionStatusResponse(
        opportunity_id=opportunity_id,
        is_saved=interaction.is_saved,
        is_followed=interaction.is_followed,
        notes=interaction.notes,
    )


@router.delete("/{user_id}/opportunities/{opportunity_id}/follow", response_model=UserInteractionStatusResponse)
async def unfollow_opportunity(
    user_id: str,
    opportunity_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Unfollow an opportunity."""
    await get_user_or_404(user_id, db, current_user=current_user)
    interaction = await _get_or_create_interaction(user_id, opportunity_id, db)
    interaction.is_followed = False
    await db.commit()
    await db.refresh(interaction)
    return UserInteractionStatusResponse(
        opportunity_id=opportunity_id,
        is_saved=interaction.is_saved,
        is_followed=interaction.is_followed,
        notes=interaction.notes,
    )


@router.get("/{user_id}/saved", response_model=PaginatedResponse[OpportunityRead])
async def list_saved_opportunities(
    user_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """List opportunities bookmarked by the user."""
    await get_user_or_404(user_id, db, current_user=current_user)

    count_stmt = (
        select(func.count(Opportunity.id))
        .join(UserOpportunityInteraction, UserOpportunityInteraction.opportunity_id == Opportunity.id)
        .where(
            UserOpportunityInteraction.user_id == user_id,
            UserOpportunityInteraction.is_saved == True,
        )
    )
    total = (await db.execute(count_stmt)).scalar() or 0

    stmt = (
        select(Opportunity)
        .join(UserOpportunityInteraction, UserOpportunityInteraction.opportunity_id == Opportunity.id)
        .where(
            UserOpportunityInteraction.user_id == user_id,
            UserOpportunityInteraction.is_saved == True,
        )
        .order_by(UserOpportunityInteraction.updated_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = (await db.execute(stmt)).scalars().all()

    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total > 0 else 1,
    )


@router.get("/{user_id}/followed", response_model=PaginatedResponse[OpportunityRead])
async def list_followed_opportunities(
    user_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """List opportunities followed by the user for lifecycle alerts."""
    await get_user_or_404(user_id, db, current_user=current_user)

    count_stmt = (
        select(func.count(Opportunity.id))
        .join(UserOpportunityInteraction, UserOpportunityInteraction.opportunity_id == Opportunity.id)
        .where(
            UserOpportunityInteraction.user_id == user_id,
            UserOpportunityInteraction.is_followed == True,
        )
    )
    total = (await db.execute(count_stmt)).scalar() or 0

    stmt = (
        select(Opportunity)
        .join(UserOpportunityInteraction, UserOpportunityInteraction.opportunity_id == Opportunity.id)
        .where(
            UserOpportunityInteraction.user_id == user_id,
            UserOpportunityInteraction.is_followed == True,
        )
        .order_by(UserOpportunityInteraction.updated_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = (await db.execute(stmt)).scalars().all()

    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total > 0 else 1,
    )
