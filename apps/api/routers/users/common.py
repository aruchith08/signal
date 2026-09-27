"""
Common authorization and database helper functions for user routers
"""
from typing import Optional
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from apps.api.config import settings
from apps.api.models.user import User
from apps.api.models.skill import UserSkill


def verify_user_access(user_id: str, current_user: Optional[User]) -> None:
    """Enforce authorization and IDOR protection on user-scoped resources."""
    if current_user is not None:
        if current_user.id != user_id and not (current_user.is_superuser or current_user.role == "admin"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: Cannot access or modify another user's resources",
            )


async def get_user_or_404(
    user_id: str,
    db: AsyncSession,
    current_user: Optional[User] = None,
) -> User:
    """Fetch user by id with eager-loaded profile/preferences or raise 404/403."""
    if current_user is not None or settings.ENVIRONMENT == "production":
        verify_user_access(user_id, current_user)

    stmt = (
        select(User)
        .where(User.id == user_id)
        .options(
            selectinload(User.profile),
            selectinload(User.interests),
            selectinload(User.skills).selectinload(UserSkill.skill),
            selectinload(User.preferences),
        )
    )
    user = (await db.execute(stmt)).scalars().first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User '{user_id}' not found")
    return user
