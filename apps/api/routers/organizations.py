"""
Organizations API Router
"""
import math
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select

from apps.api.database import get_db
from apps.api.models.organization import Organization
from apps.api.schemas.common import PaginatedResponse
from apps.api.schemas.organization import (
    OrganizationCreate,
    OrganizationRead,
    OrganizationUpdate,
)
from shared.utils import slugify

router = APIRouter(prefix="/organizations", tags=["Organizations"])


@router.get("", response_model=PaginatedResponse[OrganizationRead])
async def list_organizations(
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
):
    """List organizations with optional search and pagination."""
    query = select(Organization)
    if search:
        query = query.where(Organization.name.ilike(f"%{search}%"))

    count_stmt = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    query = query.order_by(Organization.name).offset((page - 1) * page_size).limit(page_size)
    items = (await db.execute(query)).scalars().all()

    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total > 0 else 1,
    )


@router.post("", response_model=OrganizationRead, status_code=status.HTTP_201_CREATED)
async def create_organization(
    data: OrganizationCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new organization."""
    slug = data.slug or slugify(data.name)
    existing = (await db.execute(select(Organization).where(Organization.slug == slug))).scalars().first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Organization with slug '{slug}' already exists.",
        )

    org = Organization(
        name=data.name,
        slug=slug,
        website=data.website,
        logo_url=data.logo_url,
        description=data.description,
        is_verified=data.is_verified,
    )
    db.add(org)
    await db.commit()
    await db.refresh(org)
    return org


@router.get("/{id}", response_model=OrganizationRead)
async def get_organization(
    id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get an organization by ID."""
    org = (await db.execute(select(Organization).where(Organization.id == id))).scalars().first()
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    return org
