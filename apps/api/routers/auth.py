"""
Authentication API Router (Register, Login, Me)
"""
from datetime import timedelta
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from apps.api.config import settings
from apps.api.core.auth import (
    create_access_token,
    get_current_active_user,
    hash_password,
    verify_password,
)
from apps.api.database import get_db
from apps.api.models.preference import UserNotificationPreference
from apps.api.models.user import User, UserProfile
from apps.api.schemas.auth import TokenResponse, UserLogin, UserRegister
from apps.api.schemas.user import UserRead

logger = logging.getLogger("signal.api.auth_router")
router = APIRouter(prefix="/auth", tags=["Authentication & Security"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: UserRegister, db: AsyncSession = Depends(get_db)):
    """Register a new user account with hashed password and generate an access token."""
    existing_stmt = select(User).where(
        (User.email == payload.email) | (User.username == payload.username)
    )
    existing = (await db.execute(existing_stmt)).scalars().first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email or username already exists",
        )

    # Hash the password
    pw_hash = hash_password(payload.password)

    user = User(
        email=payload.email,
        username=payload.username,
        full_name=payload.full_name,
        hashed_password=pw_hash,
        role="user",
        is_active=True,
        is_superuser=False,
    )
    db.add(user)
    await db.flush()

    # Automatically initialize default profile and notification preferences
    profile = UserProfile(user_id=user.id)
    pref = UserNotificationPreference(user_id=user.id)
    db.add(profile)
    db.add(pref)
    await db.commit()

    # Eager reload for response
    stmt = (
        select(User)
        .where(User.id == user.id)
        .options(
            selectinload(User.profile),
            selectinload(User.interests),
            selectinload(User.preferences),
        )
    )
    loaded_user = (await db.execute(stmt)).scalars().first()

    expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    token = create_access_token(
        data={"sub": loaded_user.id, "username": loaded_user.username, "role": loaded_user.role},
        expires_delta=expires_delta,
    )

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=loaded_user,
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Authenticate user via JSON body or Form Data and return JWT bearer token.
    """
    content_type = request.headers.get("content-type", "")
    username = None
    password = None

    if "application/json" in content_type:
        try:
            body = await request.json()
            if isinstance(body, dict):
                username = body.get("username")
                password = body.get("password")
        except Exception:
            pass
    elif "form" in content_type:
        try:
            form = await request.form()
            username = form.get("username")
            password = form.get("password")
        except Exception:
            pass
    else:
        try:
            body = await request.json()
            if isinstance(body, dict):
                username = body.get("username")
                password = body.get("password")
        except Exception:
            try:
                form = await request.form()
                username = form.get("username")
                password = form.get("password")
            except Exception:
                pass

    if not username or not password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username and password are required",
        )


    stmt = (
        select(User)
        .where((User.username == username) | (User.email == username))
        .options(
            selectinload(User.profile),
            selectinload(User.interests),
            selectinload(User.preferences),
        )
    )
    user = (await db.execute(stmt)).scalars().first()

    if not user or not user.hashed_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User account is inactive",
        )

    expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    token = create_access_token(
        data={"sub": user.id, "username": user.username, "role": user.role},
        expires_delta=expires_delta,
    )

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=user,
    )


@router.get("/me", response_model=UserRead)
async def get_current_user_profile(
    current_user: User = Depends(get_current_active_user),
):
    """Retrieve details of the currently authenticated user."""
    return current_user
