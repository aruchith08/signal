"""
Hierarchical Deterministic Entity Resolution Engine
Resolves incoming announcements to existing canonical opportunities using 5 conservative tiers:
1. External ID
2. Canonical Application URL
3. Exact Normalized Title + Organization
4. Opportunity Alias Match
5. Conservative Token Similarity (with strict false-merge guardrails)
"""
import logging
import re
from typing import List, Optional, Set
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import or_, select

from apps.api.models.opportunity import Opportunity
from apps.api.models.alias import OpportunityAlias
from apps.api.models.discovery import RawDiscovery
from shared.constants import MatchReason
from shared.utils import canonicalize_url, normalize_title

logger = logging.getLogger("signal.entity_resolution")


class EntityMatchResult(BaseModel):
    """Result of entity resolution check."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    matched: bool
    opportunity: Optional[Opportunity] = None
    confidence: float = 0.0
    reason: MatchReason = MatchReason.NEW_ENTITY
    details: str = ""


class EntityResolver:
    """Multi-tiered conservative deterministic entity matcher."""

    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def tokenize(text: str) -> Set[str]:
        """Convert text into normalized set of alpha-numeric word tokens."""
        if not text:
            return set()
        cleaned = re.sub(r"[^\w\s]", " ", text.lower())
        tokens = set(cleaned.split())
        # Filter common non-discriminative stop words
        stop_words = {
            "the", "a", "an", "and", "or", "for", "in", "of", "to", "at",
            "is", "are", "now", "open", "live", "details", "update", "updates",
            "announced", "announces", "registrations", "registration", "deadline",
            "extended", "results", "declared", "dates", "date", "status"
        }
        return tokens - stop_words

    async def resolve(
        self,
        title: str,
        canonical_name: Optional[str] = None,
        canonical_url: Optional[str] = None,
        external_id: Optional[str] = None,
        organization_id: Optional[str] = None,
        season: Optional[str] = None,
        year: Optional[int] = None,
    ) -> EntityMatchResult:
        """
        Evaluate candidate against existing opportunities through hierarchical matching tiers.
        """
        # --- Level 1: External ID Match ---
        if external_id:
            # Check if any prior RawDiscovery with this external_id is already linked to an Opportunity
            disc_stmt = select(RawDiscovery).where(
                RawDiscovery.external_id == external_id,
                RawDiscovery.opportunity_id.isnot(None),
            )
            prior_disc = (await self.db.execute(disc_stmt)).scalars().first()
            if prior_disc and prior_disc.opportunity_id:
                opp_stmt = select(Opportunity).where(Opportunity.id == prior_disc.opportunity_id)
                opp = (await self.db.execute(opp_stmt)).scalars().first()
                if opp:
                    logger.info(f"[EntityResolver] Level 1 match by External ID '{external_id}': {opp.id} ('{opp.title}')")
                    return EntityMatchResult(
                        matched=True,
                        opportunity=opp,
                        confidence=1.0,
                        reason=MatchReason.EXACT_EXTERNAL_ID,
                        details=f"Matched external_id='{external_id}' via prior discovery",
                    )

        # --- Level 2: Canonical URL Match ---
        if canonical_url:
            clean_url = canonicalize_url(canonical_url)
            stmt = select(Opportunity).where(Opportunity.application_url == clean_url)
            opp = (await self.db.execute(stmt)).scalars().first()
            if opp:
                logger.info(f"[EntityResolver] Level 2 match by Canonical URL: {opp.id} ('{opp.title}')")
                return EntityMatchResult(
                    matched=True,
                    opportunity=opp,
                    confidence=0.98,
                    reason=MatchReason.CANONICAL_URL,
                    details=f"Matched canonical_url='{clean_url}'",
                )

        # --- Level 3: Exact Normalized Title + Organization Match ---
        norm_title = normalize_title(title)
        norm_canonical = normalize_title(canonical_name) if canonical_name else ""

        if organization_id and (norm_title or norm_canonical):
            filters = [Opportunity.title.ilike(f"%{norm_title}%")]
            if norm_canonical:
                filters.append(Opportunity.canonical_name.ilike(f"%{norm_canonical}%"))
                filters.append(Opportunity.title.ilike(f"%{norm_canonical}%"))
            filters.append(Opportunity.canonical_name.ilike(f"%{norm_title}%"))

            stmt = (
                select(Opportunity)
                .where(
                    Opportunity.organization_id == organization_id,
                    or_(*filters),
                )
                .limit(25)
            )
            candidates = (await self.db.execute(stmt)).scalars().all()

            for opp in candidates:
                opp_norm = normalize_title(opp.title)
                opp_canon_norm = normalize_title(opp.canonical_name or "")
                
                # Compare title or canonical name
                if (norm_title and norm_title == opp_norm) or \
                   (norm_canonical and norm_canonical == opp_canon_norm) or \
                   (norm_canonical and norm_canonical == opp_norm) or \
                   (norm_title and norm_title == opp_canon_norm):
                    # Check for conflicting year or season
                    if year and opp.year and year != opp.year:
                        continue
                    if season and opp.season and season != opp.season:
                        continue

                    logger.info(f"[EntityResolver] Level 3 match by Title + Org: {opp.id} ('{opp.title}')")
                    return EntityMatchResult(
                        matched=True,
                        opportunity=opp,
                        confidence=0.95,
                        reason=MatchReason.EXACT_TITLE_ORGANIZATION,
                        details=f"Exact normalized title match for organization '{organization_id}'",
                    )

        # --- Level 4: Opportunity Alias Match ---
        alias_stmt = select(OpportunityAlias).where(
            OpportunityAlias.alias.ilike(title)
        )
        alias_record = (await self.db.execute(alias_stmt)).scalars().first()
        if not alias_record and canonical_name:
            alias_stmt = select(OpportunityAlias).where(
                OpportunityAlias.alias.ilike(canonical_name)
            )
            alias_record = (await self.db.execute(alias_stmt)).scalars().first()

        if alias_record:
            opp_stmt = select(Opportunity).where(Opportunity.id == alias_record.opportunity_id)
            opp = (await self.db.execute(opp_stmt)).scalars().first()
            if opp:
                logger.info(f"[EntityResolver] Level 4 match by Alias: {opp.id} ('{opp.title}') via '{alias_record.alias}'")
                return EntityMatchResult(
                    matched=True,
                    opportunity=opp,
                    confidence=0.92,
                    reason=MatchReason.ALIAS,
                    details=f"Matched known alias '{alias_record.alias}'",
                )

        # --- Level 5: Conservative Deterministic Token Similarity ---
        # Only compare opportunities within the SAME organization to strictly prevent false cross-organization merges
        if organization_id:
            candidate_tokens = self.tokenize(title) | self.tokenize(canonical_name or "")
            if candidate_tokens:
                token_filters = []
                for token in list(candidate_tokens)[:6]:
                    pattern = f"%{token}%"
                    token_filters.append(Opportunity.title.ilike(pattern))
                    token_filters.append(Opportunity.canonical_name.ilike(pattern))

                stmt = (
                    select(Opportunity)
                    .where(
                        Opportunity.organization_id == organization_id,
                        or_(*token_filters),
                    )
                    .limit(50)
                )
                candidates = (await self.db.execute(stmt)).scalars().all()
            else:
                candidates = []

            best_opp = None
            best_score = 0.0

            for opp in candidates:
                # 1. Guardrail: Conflicting explicit year or season
                if year and opp.year and year != opp.year:
                    continue
                if season and opp.season and season != opp.season:
                    continue

                opp_tokens = self.tokenize(opp.title) | self.tokenize(opp.canonical_name or "")
                if not opp_tokens or not candidate_tokens:
                    continue

                # Token Overlap (Jaccard similarity on discriminative tokens)
                intersection = candidate_tokens & opp_tokens
                union = candidate_tokens | opp_tokens
                jaccard = len(intersection) / len(union) if union else 0.0

                # Token containment check (e.g. "TCS CodeVita" is completely contained in "TCS CodeVita Season 13")
                is_contained = opp_tokens.issubset(candidate_tokens) or candidate_tokens.issubset(opp_tokens)

                if is_contained and len(intersection) >= 1:
                    score = max(jaccard, 0.86)
                else:
                    score = jaccard

                if score > best_score and score >= 0.70:
                    best_score = score
                    best_opp = opp

            if best_opp and best_score >= 0.70:
                logger.info(
                    f"[EntityResolver] Level 5 conservative similarity match: {best_opp.id} ('{best_opp.title}') "
                    f"with score {best_score:.2f}"
                )
                return EntityMatchResult(
                    matched=True,
                    opportunity=best_opp,
                    confidence=round(best_score, 2),
                    reason=MatchReason.DETERMINISTIC_SIMILARITY,
                    details=f"Conservative token match score={best_score:.2f} within same organization",
                )

        # No match found -> new canonical entity
        return EntityMatchResult(
            matched=False,
            opportunity=None,
            confidence=0.0,
            reason=MatchReason.NEW_ENTITY,
            details="No matching existing opportunity found",
        )
