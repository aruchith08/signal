"""
User Weighted Interests Endpoints
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from apps.api.database import get_db
from apps.api.models.user import User, UserInterest
from apps.api.schemas.user import (
    UserInterestCreate,
    UserInterestRead,
    UserInterestUpdate,
)
from apps.api.core.auth import get_current_user_optional
from apps.api.routers.users.common import get_user_or_404

router = APIRouter()


@router.get("/{user_id}/interests", response_model=List[UserInterestRead])
async def list_user_interests(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """List weighted interest tags for a user."""
    user = await get_user_or_404(user_id, db, current_user=current_user)
    return user.interests or []


@router.post("/{user_id}/interests", response_model=UserInterestRead, status_code=status.HTTP_201_CREATED)
async def add_user_interest(
    user_id: str,
    payload: UserInterestCreate,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Add a new weighted interest tag."""
    user = await get_user_or_404(user_id, db, current_user=current_user)

    # Check for existing interest tag
    existing_stmt = select(UserInterest).where(
        UserInterest.user_id == user.id,
        UserInterest.category == payload.category,
        UserInterest.tag == payload.tag,
    )
    existing = (await db.execute(existing_stmt)).scalars().first()
    if existing:
        existing.weight = payload.weight
        await db.commit()
        await db.refresh(existing)
        return existing

    interest = UserInterest(
        user_id=user.id,
        category=payload.category,
        tag=payload.tag,
        weight=payload.weight,
    )
    db.add(interest)
    await db.commit()
    await db.refresh(interest)
    return interest


@router.put("/{user_id}/interests/{interest_id}", response_model=UserInterestRead)
async def update_user_interest(
    user_id: str,
    interest_id: str,
    payload: UserInterestUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Update weight or tags for an existing interest."""
    await get_user_or_404(user_id, db, current_user=current_user)
    stmt = select(UserInterest).where(UserInterest.id == interest_id, UserInterest.user_id == user_id)
    interest = (await db.execute(stmt)).scalars().first()
    if not interest:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interest not found")

    if payload.weight is not None:
        interest.weight = payload.weight
    if payload.category is not None:
        interest.category = payload.category
    if payload.tag is not None:
        interest.tag = payload.tag

    await db.commit()
    await db.refresh(interest)
    return interest


@router.delete("/{user_id}/interests/{interest_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user_interest(
    user_id: str,
    interest_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Delete an interest tag."""
    await get_user_or_404(user_id, db, current_user=current_user)
    stmt = select(UserInterest).where(UserInterest.id == interest_id, UserInterest.user_id == user_id)
    interest = (await db.execute(stmt)).scalars().first()
    if not interest:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interest not found")

    await db.delete(interest)
    await db.commit()
    return None
