"""
Human Review Queue Service
Manages creation, filtering, manual approval, and rejection of ambiguous matches or conflicts.
"""
from datetime import datetime, timezone
import logging
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from apps.api.models.verification import VerificationReview, SemanticMatchCandidate, VerificationConflict
from shared.constants import ReviewPriority, ReviewStatus, CandidateStatus

logger = logging.getLogger("signal.review_queue")


class ReviewQueueService:
    """Manages the human-in-the-loop review queue for verification ambiguities."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def enqueue_review(
        self,
        entity_id: str,
        reason: str,
        priority: ReviewPriority = ReviewPriority.MEDIUM,
        candidate_id: Optional[str] = None,
        conflict_id: Optional[str] = None,
        entity_type: str = "opportunity",
    ) -> VerificationReview:
        """Enqueue an item for human review."""
        review = VerificationReview(
            entity_type=entity_type,
            entity_id=entity_id,
            candidate_id=candidate_id,
            conflict_id=conflict_id,
            reason=reason,
            priority=priority.value,
            status=ReviewStatus.OPEN.value,
        )
        self.db.add(review)
        await self.db.flush()
        logger.info(f"[ReviewQueue] Enqueued review {review.id} for {entity_type} {entity_id}: {reason}")
        return review

    async def get_queue(
        self,
        status: Optional[str] = ReviewStatus.OPEN.value,
        priority: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[VerificationReview]:
        """Fetch queue items with optional status and priority filtering."""
        stmt = select(VerificationReview)
        if status:
            stmt = stmt.where(VerificationReview.status == status)
        if priority:
            stmt = stmt.where(VerificationReview.priority == priority)
        stmt = stmt.order_by(VerificationReview.created_at.desc()).limit(limit).offset(offset)
        return list((await self.db.execute(stmt)).scalars().all())

    async def approve_review(
        self,
        review_id: str,
        notes: Optional[str] = None,
    ) -> Optional[VerificationReview]:
        """Mark review approved and resolve linked candidate or conflict."""
        stmt = select(VerificationReview).where(VerificationReview.id == review_id)
        review = (await self.db.execute(stmt)).scalars().first()
        if not review:
            return None

        review.status = ReviewStatus.APPROVED.value
        review.resolution_action = "APPROVED"
        review.review_notes = notes
        review.resolved_at = datetime.now(timezone.utc)

        # If linked candidate exists, update status
        if review.candidate_id:
            cand_stmt = select(SemanticMatchCandidate).where(SemanticMatchCandidate.id == review.candidate_id)
            candidate = (await self.db.execute(cand_stmt)).scalars().first()
            if candidate:
                candidate.status = CandidateStatus.MERGED.value
                candidate.resolved_at = datetime.now(timezone.utc)

        await self.db.flush()
        logger.info(f"[ReviewQueue] Approved review {review_id}")
        return review

    async def reject_review(
        self,
        review_id: str,
        notes: Optional[str] = None,
    ) -> Optional[VerificationReview]:
        """Mark review rejected and keep opportunities separate."""
        stmt = select(VerificationReview).where(VerificationReview.id == review_id)
        review = (await self.db.execute(stmt)).scalars().first()
        if not review:
            return None

        review.status = ReviewStatus.REJECTED.value
        review.resolution_action = "REJECTED"
        review.review_notes = notes
        review.resolved_at = datetime.now(timezone.utc)

        if review.candidate_id:
            cand_stmt = select(SemanticMatchCandidate).where(SemanticMatchCandidate.id == review.candidate_id)
            candidate = (await self.db.execute(cand_stmt)).scalars().first()
            if candidate:
                candidate.status = CandidateStatus.REJECTED.value
                candidate.resolved_at = datetime.now(timezone.utc)

        await self.db.flush()
        logger.info(f"[ReviewQueue] Rejected review {review_id}")
        return review
