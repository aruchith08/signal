"""
Deduplication Engine — Multi-strategy matching and future semantic extension point
"""
import logging
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from apps.api.models.opportunity import Opportunity
from shared.utils import compute_content_hash, canonicalize_url, normalize_title

logger = logging.getLogger(__name__)


class Deduplicator:
    """
    Evaluates incoming candidates against stored opportunities to detect duplicates.
    Supports exact content hash, canonical URL matching, normalized title/org matching,
    and provides a clean hook for Phase 3 semantic embeddings.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def find_duplicate(
        self,
        raw_content: str,
        application_url: Optional[str] = None,
        title: Optional[str] = None,
        organization_id: Optional[str] = None,
    ) -> Optional[Opportunity]:
        """
        Check whether an opportunity already exists across several matching levels:
        1. Content Hash (exact normalized text match)
        2. Canonical Application URL
        3. Normalized Title + Organization match
        4. Semantic Similarity (Future extension point for Phase 3)
        """
        # Level 1: Content Hash Match
        if raw_content:
            content_hash = compute_content_hash(raw_content)
            stmt = select(Opportunity).where(Opportunity.content_hash == content_hash)
            existing = (await self.db.execute(stmt)).scalars().first()
            if existing:
                logger.info(f"[Deduplicator] Matched existing opportunity by content hash: {existing.id} ('{existing.title}')")
                return existing

        # Level 2: Canonical Application URL Match
        if application_url:
            canonical_url = canonicalize_url(application_url)
            stmt = select(Opportunity).where(Opportunity.application_url == canonical_url)
            existing = (await self.db.execute(stmt)).scalars().first()
            if existing:
                logger.info(f"[Deduplicator] Matched existing opportunity by application URL: {existing.id} ('{existing.title}')")
                return existing

        # Level 3: Normalized Title + Organization Match
        if title:
            norm_title = normalize_title(title)
            query = select(Opportunity)
            if organization_id:
                query = query.where(Opportunity.organization_id == organization_id)
            candidates = (await self.db.execute(query)).scalars().all()
            for cand in candidates:
                if normalize_title(cand.title) == norm_title:
                    logger.info(f"[Deduplicator] Matched existing opportunity by normalized title/org: {cand.id} ('{cand.title}')")
                    return cand

        # Level 4: Semantic Similarity (Reserved for Phase 3 embeddings)
        # return await self._semantic_similarity_check(...)
        return None

    async def _semantic_similarity_check(self, title: str, summary: str) -> Optional[Opportunity]:
        """
        Future extension point: Compute vector embedding and search with cosine similarity threshold.
        Intentionally postponed to Phase 3 per architectural plan.
        """
        return None
