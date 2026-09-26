"""
Users & Personalization Router Module
Aggregates focused sub-routers for Profile, Preferences, Interests, Skills, and Interactions.
"""
from fastapi import APIRouter

from apps.api.routers.users.common import get_user_or_404, verify_user_access
from apps.api.routers.users.base import router as base_router
from apps.api.routers.users.profile import router as profile_router
from apps.api.routers.users.preferences import router as preferences_router
from apps.api.routers.users.interests import router as interests_router
from apps.api.routers.users.skills import router as skills_router
from apps.api.routers.users.interactions import router as interactions_router

router = APIRouter(prefix="/users", tags=["Users & Personalization"])

# Include sub-routers maintaining exact identical URL hierarchy
router.include_router(base_router)
router.include_router(profile_router)
router.include_router(preferences_router)
router.include_router(interests_router)
router.include_router(skills_router)
router.include_router(interactions_router)

__all__ = [
    "router",
    "get_user_or_404",
    "verify_user_access",
]
