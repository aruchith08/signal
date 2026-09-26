"""
User Skills Endpoints
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from apps.api.database import get_db
from apps.api.models.user import User
from apps.api.models.skill import Skill, UserSkill
from apps.api.schemas.skill import (
    UserSkillCreate,
    UserSkillRead,
)
from apps.api.core.auth import get_current_user_optional
from apps.api.routers.users.common import get_user_or_404

router = APIRouter()


@router.get("/{user_id}/skills", response_model=List[UserSkillRead])
async def list_user_skills(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """List skills associated with a user."""
    user = await get_user_or_404(user_id, db, current_user=current_user)
    return user.skills or []


@router.post("/{user_id}/skills", response_model=UserSkillRead, status_code=status.HTTP_201_CREATED)
async def add_user_skill(
    user_id: str,
    payload: UserSkillCreate,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Add a skill to user profile (creates Skill record dynamically if new)."""
    user = await get_user_or_404(user_id, db, current_user=current_user)

    clean_name = payload.skill_name.strip()
    clean_slug = clean_name.lower().replace(" ", "-").replace("+", "p").replace("#", "sharp")

    # Get or create Skill
    skill_stmt = select(Skill).where(Skill.slug == clean_slug)
    skill = (await db.execute(skill_stmt)).scalars().first()
    if not skill:
        skill = Skill(name=clean_name, slug=clean_slug, category=payload.category)
        db.add(skill)
        await db.flush()

    # Get or create UserSkill
    user_skill_stmt = select(UserSkill).where(UserSkill.user_id == user.id, UserSkill.skill_id == skill.id)
    user_skill = (await db.execute(user_skill_stmt)).scalars().first()
    if user_skill:
        user_skill.proficiency_level = payload.proficiency_level
    else:
        user_skill = UserSkill(
            user_id=user.id,
            skill_id=skill.id,
            proficiency_level=payload.proficiency_level,
        )
        db.add(user_skill)

    await db.commit()
    await db.refresh(user_skill)
    return user_skill


@router.delete("/{user_id}/skills/{skill_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user_skill(
    user_id: str,
    skill_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Remove a skill from user profile."""
    await get_user_or_404(user_id, db, current_user=current_user)
    stmt = select(UserSkill).where(UserSkill.id == skill_id, UserSkill.user_id == user_id)
    user_skill = (await db.execute(stmt)).scalars().first()
    if not user_skill:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User skill not found")

    await db.delete(user_skill)
    await db.commit()
    return None
