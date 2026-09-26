"""
Verification & Cross-Source Intelligence Endpoints
Exposes opportunity verification overviews, contributing sources, field conflicts, and review queue actions.
"""
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from apps.api.database import get_db
from apps.api.models.opportunity import Opportunity
from apps.api.models.verification import (
    OpportunitySource,
    VerificationConflict,
    VerificationReview,
)
from apps.api.schemas.verification import (
    OpportunitySourceResponse,
    OpportunityVerificationOverview,
    ReviewActionRequest,
    QueueResolutionRequest,
    ConflictResolutionRequest,
    VerificationConflictResponse,
    VerificationReviewResponse,
)
from apps.api.config import settings
from apps.api.core.auth import get_current_user_optional
from apps.api.models.user import User
from services.verification.review_queue import ReviewQueueService

logger = logging.getLogger("signal.api.verification")
router = APIRouter(prefix="", tags=["Verification & Cross-Source Intelligence"])


def verify_reviewer_access(current_user: Optional[User]) -> None:
    """Enforce reviewer or admin role authorization."""
    if current_user is not None:
        if not (current_user.is_superuser or current_user.role in ["reviewer", "admin"]):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: Reviewer or admin role required",
            )
    elif settings.ENVIRONMENT == "production":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )



@router.get(
    "/opportunities/{id}/verification",
    response_model=OpportunityVerificationOverview,
    summary="Get complete verification status for an opportunity",
)
async def get_opportunity_verification(
    id: str,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Opportunity).where(Opportunity.id == id)
    opp = (await db.execute(stmt)).scalars().first()
    if not opp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Opportunity not found")

    return OpportunityVerificationOverview(
        opportunity_id=opp.id,
        title=opp.title,
        verification_status=opp.verification_status,
        verification_confidence=opp.verification_confidence,
        source_count=opp.source_count,
        official_source_present=opp.official_source_present,
        last_verified_at=opp.last_verified_at,
        sources=opp.sources,
        verified_fields=opp.verified_fields,
        conflicts=opp.conflicts,
    )


@router.get(
    "/opportunities/{id}/sources",
    response_model=List[OpportunitySourceResponse],
    summary="List all sources contributing to an opportunity",
)
async def get_opportunity_sources(
    id: str,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(OpportunitySource).where(OpportunitySource.opportunity_id == id).order_by(OpportunitySource.created_at.asc())
    sources = (await db.execute(stmt)).scalars().all()
    return list(sources)


@router.get(
    "/verification/conflicts",
    response_model=List[VerificationConflictResponse],
    summary="Query unresolved or resolved verification conflicts",
)
async def list_verification_conflicts(
    field_name: Optional[str] = Query(None, description="Filter by field name (deadline, eligibility, etc.)"),
    status: Optional[str] = Query(None, description="Filter by status (open, resolved_official, etc.)"),
    opportunity_id: Optional[str] = Query(None, description="Filter by opportunity ID"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(VerificationConflict)
    if field_name:
        stmt = stmt.where(VerificationConflict.field_name == field_name)
    if status:
        stmt = stmt.where(VerificationConflict.status == status)
    if opportunity_id:
        stmt = stmt.where(VerificationConflict.opportunity_id == opportunity_id)

    stmt = stmt.order_by(VerificationConflict.created_at.desc()).limit(limit).offset(offset)
    conflicts = (await db.execute(stmt)).scalars().all()
    return list(conflicts)


@router.get(
    "/verification/review-queue",
    response_model=List[VerificationReviewResponse],
    summary="Fetch items requiring human review",
)
async def get_review_queue(
    status: Optional[str] = Query("open", description="Filter by review status (open, approved, rejected)"),
    priority: Optional[str] = Query(None, description="Filter by priority (critical, high, medium, low)"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    verify_reviewer_access(current_user)
    service = ReviewQueueService(db)
    items = await service.get_queue(status=status, priority=priority, limit=limit, offset=offset)
    return items


@router.get(
    "/verification/queue",
    response_model=List[VerificationReviewResponse],
    summary="Alias for review queue",
    include_in_schema=False,
)
async def get_queue_alias(
    status: Optional[str] = Query(None, description="Filter by review status"),
    priority: Optional[str] = Query(None, description="Filter by priority"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    # Support 'PENDING' -> 'open'
    normalized_status = status.lower() if status else "open"
    if normalized_status == "pending":
        normalized_status = "open"
    return await get_review_queue(
        status=normalized_status,
        priority=priority,
        limit=limit,
        offset=offset,
        db=db,
        current_user=current_user,
    )


@router.post(
    "/verification/review/{id}/approve",
    response_model=VerificationReviewResponse,
    summary="Approve a human review item",
)
async def approve_review_item(
    id: str,
    payload: Optional[ReviewActionRequest] = None,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    verify_reviewer_access(current_user)
    service = ReviewQueueService(db)
    notes = payload.notes if payload else None
    review = await service.approve_review(id, notes=notes)
    if not review:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review item not found")
    await db.commit()
    return review


@router.post(
    "/verification/review/{id}/reject",
    response_model=VerificationReviewResponse,
    summary="Reject a human review item",
)
async def reject_review_item(
    id: str,
    payload: Optional[ReviewActionRequest] = None,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    verify_reviewer_access(current_user)
    service = ReviewQueueService(db)
    notes = payload.notes if payload else None
    review = await service.reject_review(id, notes=notes)
    if not review:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review item not found")
    await db.commit()
    return review


@router.post(
    "/verification/queue/{id}/resolve",
    response_model=VerificationReviewResponse,
    summary="Resolve a human review item by action (APPROVE, REJECT, MERGE)",
)
@router.post(
    "/verification/review/{id}/resolve",
    response_model=VerificationReviewResponse,
    include_in_schema=False,
)
async def resolve_review_item(
    id: str,
    payload: QueueResolutionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    verify_reviewer_access(current_user)
    action = payload.action.upper()
    service = ReviewQueueService(db)
    if action in ("APPROVE", "MERGE"):
        review = await service.approve_review(id, notes=payload.notes)
    elif action == "REJECT":
        review = await service.reject_review(id, notes=payload.notes)
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unsupported action: {payload.action}")

    if not review:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review item not found")
    await db.commit()
    return review


@router.post(
    "/verification/conflicts/{id}/resolve",
    response_model=VerificationConflictResponse,
    summary="Resolve a verification conflict with manual authoritative value",
)
async def resolve_conflict_item(
    id: str,
    payload: ConflictResolutionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    verify_reviewer_access(current_user)
    stmt = select(VerificationConflict).where(VerificationConflict.id == id)
    conflict = (await db.execute(stmt)).scalars().first()
    if not conflict:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Verification conflict not found")

    conflict.status = "resolved_manual"
    notes = f"Strategy: {payload.resolution_strategy}. Resolved to: {payload.resolved_value}"
    if payload.notes:
        notes += f" | Notes: {payload.notes}"
    conflict.resolution_notes = notes

    await db.commit()
    await db.refresh(conflict)
    return conflict

