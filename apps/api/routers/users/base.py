"""
Base User, Relevance, and Notification History Endpoints
"""
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from apps.api.database import get_db
from apps.api.models.user import User, UserProfile, UserInterest
from apps.api.models.skill import UserSkill
from apps.api.models.preference import UserNotificationPreference
from apps.api.models.opportunity import Opportunity
from apps.api.models.notification import Notification
from apps.api.schemas.user import UserRead, UserCreate
from apps.api.schemas.relevance import RelevanceResultRead
from apps.api.schemas.notification import NotificationRead
from apps.api.core.auth import get_current_user_optional, hash_password
from apps.api.routers.users.common import get_user_or_404
from services.personalization.relevance_engine import PersonalizationEngine

logger = logging.getLogger("signal.api.users.base")
router = APIRouter()


@router.post("/", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user(payload: UserCreate, db: AsyncSession = Depends(get_db)):
    """Create a new user."""
    existing_stmt = select(User).where((User.email == payload.email) | (User.username == payload.username))
    existing = (await db.execute(existing_stmt)).scalars().first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email or username already exists")

    hashed_password = hash_password(payload.password) if payload.password else None
    user = User(
        email=payload.email,
        username=payload.username,
        full_name=payload.full_name,
        role=payload.role,
        hashed_password=hashed_password,
        is_active=payload.is_active,
        is_superuser=payload.is_superuser,
    )
    db.add(user)
    await db.flush()

    # Create default empty profile and preferences
    profile = UserProfile(user_id=user.id)
    pref = UserNotificationPreference(user_id=user.id)
    db.add(profile)
    db.add(pref)
    await db.commit()
    await db.refresh(user)
    return user


@router.get("/active", response_model=UserRead)
async def get_active_user(db: AsyncSession = Depends(get_db)):
    """Fetch the active development user, bootstrapping a default student profile if database has no users."""
    stmt = (
        select(User)
        .options(
            selectinload(User.profile),
            selectinload(User.interests),
            selectinload(User.skills).selectinload(UserSkill.skill),
            selectinload(User.preferences),
        )
        .order_by(User.created_at.asc())
    )
    user = (await db.execute(stmt)).scalars().first()
    if user:
        return user

    # Bootstrap default demo student user
    user = User(
        email="alex.chen@student.signal.dev",
        username="alex_chen",
        full_name="Alex Chen",
        is_active=True,
        is_superuser=False,
    )
    db.add(user)
    await db.flush()

    profile = UserProfile(
        user_id=user.id,
        education_level="Undergraduate",
        degree="B.Tech",
        branch="Computer Science & Engineering",
        current_year=3,
        graduation_year=2026,
        country="India",
        state="Karnataka",
        timezone="Asia/Kolkata",
        career_interests="Software Engineering, Distributed Systems, AI/ML",
        preferred_opportunity_types="hackathon, competitive_programming, internship",
        bio="3rd Year CSE student passionate about competitive programming, hackathons, and open source development.",
    )
    pref = UserNotificationPreference(
        user_id=user.id,
        enabled=True,
        min_relevance_score=60,
        instant_alerts_enabled=True,
        digest_enabled=True,
        quiet_hours_enabled=False,
        max_alerts_per_day=10,
    )
    db.add(profile)
    db.add(pref)

    # Seed core interests
    interests_data = [
        ("competitive_programming", "algorithms", 1.0),
        ("hackathon", "ai", 0.9),
        ("hackathon", "web3", 0.7),
        ("internship", "software_engineering", 1.0),
        ("fellowship", "open_source", 0.8),
        ("government", "innovation", 0.7),
    ]
    for cat, tag, wt in interests_data:
        db.add(UserInterest(user_id=user.id, category=cat, tag=tag, weight=wt))

    await db.commit()
    return await get_user_or_404(user.id, db)


@router.get("/{user_id}", response_model=UserRead)
async def get_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Fetch user basic details."""
    return await get_user_or_404(user_id, db, current_user=current_user)


@router.get("/{user_id}/opportunities/{opportunity_id}/relevance", response_model=RelevanceResultRead)
async def get_opportunity_relevance(
    user_id: str,
    opportunity_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Evaluate personalized relevance score and explainability reasons."""
    user = await get_user_or_404(user_id, db, current_user=current_user)

    opp_stmt = select(Opportunity).where(Opportunity.id == opportunity_id)
    opportunity = (await db.execute(opp_stmt)).scalars().first()
    if not opportunity:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Opportunity not found")

    engine = PersonalizationEngine(db)
    result = await engine.evaluate_relevance(user, opportunity)
    return result.to_dict()


@router.get("/{user_id}/notifications", response_model=List[NotificationRead])
async def list_user_notifications(
    user_id: str,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Fetch recent notification audit records for this user."""
    await get_user_or_404(user_id, db, current_user=current_user)
    stmt = (
        select(Notification)
        .where(Notification.user_id == user_id)
        .order_by(Notification.created_at.desc())
        .limit(limit)
    )
    return (await db.execute(stmt)).scalars().all()


@router.get("/{user_id}/notifications/{notification_id}", response_model=NotificationRead)
async def get_notification_detail(
    user_id: str,
    notification_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Fetch single notification detail."""
    await get_user_or_404(user_id, db, current_user=current_user)
    stmt = select(Notification).where(Notification.id == notification_id, Notification.user_id == user_id)
    notif = (await db.execute(stmt)).scalars().first()
    if notif:
        return notif
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
