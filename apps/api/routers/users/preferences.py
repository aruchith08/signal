"""
User Notification Preferences Endpoints
"""
from typing import Optional
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.database import get_db
from apps.api.models.user import User
from apps.api.models.preference import UserNotificationPreference
from apps.api.schemas.preference import (
    UserNotificationPreferenceRead,
    UserNotificationPreferenceUpdate,
)
from apps.api.core.auth import get_current_user_optional
from apps.api.routers.users.common import get_user_or_404

router = APIRouter()


@router.get("/{user_id}/preferences", response_model=UserNotificationPreferenceRead)
async def get_user_preferences(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Get user notification settings and quiet hours."""
    user = await get_user_or_404(user_id, db, current_user=current_user)
    if not user.preferences:
        pref = UserNotificationPreference(user_id=user.id)
        db.add(pref)
        await db.commit()
        await db.refresh(pref)
        return pref
    return user.preferences


@router.put("/{user_id}/preferences", response_model=UserNotificationPreferenceRead)
async def update_user_preferences(
    user_id: str,
    payload: UserNotificationPreferenceUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Update notification threshold, quiet hours, and Telegram preferences."""
    user = await get_user_or_404(user_id, db, current_user=current_user)
    pref = user.preferences
    if not pref:
        pref = UserNotificationPreference(user_id=user.id)
        db.add(pref)

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(pref, field, value)

    await db.commit()
    await db.refresh(pref)
    return pref
