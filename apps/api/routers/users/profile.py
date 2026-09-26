"""
User Academic & Career Profile Endpoints
"""
from typing import Optional
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.database import get_db
from apps.api.models.user import User, UserProfile
from apps.api.schemas.user import UserProfileRead, UserProfileUpdate
from apps.api.core.auth import get_current_user_optional
from apps.api.routers.users.common import get_user_or_404

router = APIRouter()


@router.get("/{user_id}/profile", response_model=UserProfileRead)
async def get_user_profile(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Get academic and career profile for a user."""
    user = await get_user_or_404(user_id, db, current_user=current_user)
    if not user.profile:
        profile = UserProfile(user_id=user.id)
        db.add(profile)
        await db.commit()
        await db.refresh(profile)
        return profile
    return user.profile


@router.put("/{user_id}/profile", response_model=UserProfileRead)
async def update_user_profile(
    user_id: str,
    payload: UserProfileUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Update academic and career profile for a user."""
    user = await get_user_or_404(user_id, db, current_user=current_user)
    profile = user.profile
    if not profile:
        profile = UserProfile(user_id=user.id)
        db.add(profile)

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(profile, field, value)

    await db.commit()
    await db.refresh(profile)
    return profile
