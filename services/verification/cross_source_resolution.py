"""
Cross-Source Entity Resolution Engine
Resolves incoming discoveries against existing opportunities using a 4-level staged strategy:
- Level 1: Exact Match (Confidence 1.00) -> Auto-merge
- Level 2: Strong Deterministic Match (Confidence 0.90-0.99) -> Auto-merge
- Level 3: Heuristic Match (Confidence 0.75-0.89) -> Candidate / Auto-merge if verified
- Level 4: Semantic Match (Confidence 0.60-0.89) -> Candidate for verification
Strictly invokes MergeGuardrails before any merge recommendation.
"""
import logging
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from apps.api.models.opportunity import Opportunity
from apps.api.models.alias import OpportunityAlias
from apps.api.models.discovery import RawDiscovery
from services.verification.merge_guardrails import MergeGuardrails
from services.verification.semantic_matcher import SemanticMatcher
from shared.utils import canonicalize_url, normalize_title

logger = logging.getLogger("signal.cross_source_resolver")


class CrossSourceMatchResult(BaseModel):
    """Result of cross-source opportunity resolution."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    matched: bool
    opportunity: Optional[Opportunity] = None
    confidence: float = 0.0
    match_level: str = "NONE"
    reasons: List[str] = []
    is_candidate_only: bool = False
    details: str = ""


class CrossSourceResolver:
    """Multi-level cross-source opportunity matcher with strict guardrail enforcement."""

    def __init__(self, db: AsyncSession, semantic_matcher: Optional[SemanticMatcher] = None):
        self.db = db
        self.semantic_matcher = semantic_matcher or SemanticMatcher()

    async def resolve(
        self,
        title: str,
        canonical_name: Optional[str] = None,
        canonical_url: Optional[str] = None,
        external_id: Optional[str] = None,
        organization_id: Optional[str] = None,
        organization_name: Optional[str] = None,
        category: Optional[str] = None,
        year: Optional[int] = None,
        season: Optional[str] = None,
        summary: Optional[str] = None,
    ) -> CrossSourceMatchResult:
        """Execute 4-level staged cross-source matching pipeline."""
        candidate_record = {
            "title": title,
            "canonical_name": canonical_name,
            "organization_id": organization_id,
            "organization_name": organization_name,
            "category": category,
            "year": year,
            "season": season,
            "summary": summary,
        }

        # --- LEVEL 1: EXACT MATCH (Confidence: 1.00) ---
        # 1.1 Exact External ID via prior RawDiscovery
        if external_id:
            disc_stmt = select(RawDiscovery).where(
                RawDiscovery.external_id == external_id,
                RawDiscovery.opportunity_id.isnot(None),
            )
            prior_disc = (await self.db.execute(disc_stmt)).scalars().first()
            if prior_disc and prior_disc.opportunity_id:
                opp = (
                    await self.db.execute(
                        select(Opportunity).where(Opportunity.id == prior_disc.opportunity_id)
                    )
                ).scalars().first()
                if opp:
                    guard = MergeGuardrails.evaluate(candidate_record, opp.__dict__)
                    if guard.allowed:
                        return CrossSourceMatchResult(
                            matched=True,
                            opportunity=opp,
                            confidence=1.00,
                            match_level="LEVEL_1_EXACT_EXTERNAL_ID",
                            reasons=["Exact external source ID match"],
                            is_candidate_only=False,
                            details=f"Matched external_id='{external_id}'",
                        )

        # 1.2 Exact Application URL
        if canonical_url:
            clean_url = canonicalize_url(canonical_url)
            stmt = select(Opportunity).where(Opportunity.application_url == clean_url)
            opp = (await self.db.execute(stmt)).scalars().first()
            if opp:
                guard = MergeGuardrails.evaluate(candidate_record, opp.__dict__)
                if guard.allowed:
                    return CrossSourceMatchResult(
                        matched=True,
                        opportunity=opp,
                        confidence=1.00,
                        match_level="LEVEL_1_EXACT_URL",
                        reasons=["Exact application URL match"],
                        is_candidate_only=False,
                        details=f"Matched URL: '{clean_url}'",
                    )

        # 1.3 Exact Canonical Name + Same Organization + Same Year
        norm_title = normalize_title(title)
        norm_canon = normalize_title(canonical_name) if canonical_name else ""

        if organization_id and (norm_title or norm_canon):
            stmt = select(Opportunity).where(Opportunity.organization_id == organization_id)
            org_opps = (await self.db.execute(stmt)).scalars().all()

            for opp in org_opps:
                opp_norm = normalize_title(opp.title)
                opp_canon_norm = normalize_title(opp.canonical_name or "")

                if (norm_title and norm_title in [opp_norm, opp_canon_norm]) or                    (norm_canon and norm_canon in [opp_norm, opp_canon_norm]):
                    guard = MergeGuardrails.evaluate(candidate_record, opp.__dict__)
                    if guard.allowed:
                        return CrossSourceMatchResult(
                            matched=True,
                            opportunity=opp,
                            confidence=0.98,
                            match_level="LEVEL_1_EXACT_NAME_ORG_YEAR",
                            reasons=["Exact title and organization alignment"],
                            is_candidate_only=False,
                            details=f"Exact normalized name match for org '{organization_id}'",
                        )

        # --- LEVEL 2: STRONG DETERMINISTIC MATCH (Confidence: 0.90 - 0.99) ---
        # Same organization + Compatible year + High token containment/overlap
        if organization_id:
            stmt = select(Opportunity).where(Opportunity.organization_id == organization_id)
            candidates = (await self.db.execute(stmt)).scalars().all()

            stop_words = {
                "the", "a", "an", "and", "or", "for", "in", "of", "to", "at",
                "is", "are", "now", "open", "live", "details", "update", "updates",
                "announced", "announces", "registrations", "registration", "deadline",
                "extended", "results", "declared", "dates", "date", "status"
            }
            cand_tokens = set(normalize_title(f"{title} {canonical_name or ''}").split()) - stop_words
            for opp in candidates:
                guard = MergeGuardrails.evaluate(candidate_record, opp.__dict__)
                if not guard.allowed:
                    continue

                opp_tokens = set(normalize_title(f"{opp.title} {opp.canonical_name or ''}").split()) - stop_words
                if not cand_tokens or not opp_tokens:
                    continue

                # Jaccard and containment
                intersection = cand_tokens & opp_tokens
                union = cand_tokens | opp_tokens
                jaccard = len(intersection) / len(union) if union else 0.0
                contained = opp_tokens.issubset(cand_tokens) or cand_tokens.issubset(opp_tokens)

                # If 3+ discriminative tokens overlap or Jaccard is high, it's a strong match
                if (contained and len(intersection) >= 2) or len(intersection) >= 3 or jaccard >= 0.70:
                    confidence = round(max(jaccard, 0.94), 2)
                    return CrossSourceMatchResult(
                        matched=True,
                        opportunity=opp,
                        confidence=confidence,
                        match_level="LEVEL_2_STRONG_DETERMINISTIC",
                        reasons=["High token overlap within identical organization"],
                        is_candidate_only=False,
                        details=f"Strong token match jaccard={jaccard:.2f}",
                    )

        # --- LEVEL 3: HEURISTIC MATCH (Confidence: 0.75 - 0.89) ---
        # Check aliases across opportunities
        alias_stmt = select(OpportunityAlias).where(
            (OpportunityAlias.alias.ilike(title)) |
            (OpportunityAlias.alias.ilike(canonical_name or title))
        )
        alias_record = (await self.db.execute(alias_stmt)).scalars().first()
        if alias_record:
            opp = (
                await self.db.execute(
                    select(Opportunity).where(Opportunity.id == alias_record.opportunity_id)
                )
            ).scalars().first()
            if opp:
                guard = MergeGuardrails.evaluate(candidate_record, opp.__dict__)
                if guard.allowed:
                    return CrossSourceMatchResult(
                        matched=True,
                        opportunity=opp,
                        confidence=0.88,
                        match_level="LEVEL_3_HEURISTIC_ALIAS",
                        reasons=[f"Matched established alias '{alias_record.alias}'"],
                        is_candidate_only=False,
                        details="Alias confirmed match",
                    )

        # --- LEVEL 4: SEMANTIC EMBEDDINGS (Confidence: 0.60 - 0.89) ---
        # Generates candidate relationship without automatic merge
        all_opps_stmt = select(Opportunity).options(selectinload(Opportunity.organization)).limit(50)
        all_opps = (await self.db.execute(all_opps_stmt)).scalars().all()

        cand_text = self.semantic_matcher.build_invariant_text(
            title=title,
            organization_name=organization_name,
            category=category,
            year=year,
            season=season,
            summary=summary,
        )

        best_opp: Optional[Opportunity] = None
        best_sim = 0.0

        for opp in all_opps:
            guard = MergeGuardrails.evaluate(candidate_record, opp.__dict__)
            if not guard.allowed:
                continue

            opp_text = self.semantic_matcher.build_invariant_text(
                title=opp.title,
                organization_name=opp.organization.name if opp.organization else None,
                category=opp.category,
                year=opp.year,
                season=opp.season,
                summary=opp.summary,
            )

            sim = await self.semantic_matcher.compute_similarity(cand_text, opp_text)
            if sim > best_sim and sim >= 0.65:
                best_sim = sim
                best_opp = opp

        if best_opp and best_sim >= 0.65:
            return CrossSourceMatchResult(
                matched=True,
                opportunity=best_opp,
                confidence=round(best_sim, 2),
                match_level="LEVEL_4_SEMANTIC_SIMILARITY",
                reasons=[f"Semantic embedding cosine similarity={best_sim:.2f}"],
                is_candidate_only=True,  # Embeddings require verification
                details=f"Semantic match candidate found with similarity={best_sim:.2f}",
            )

        # No match found
        return CrossSourceMatchResult(
            matched=False,
            opportunity=None,
            confidence=0.0,
            match_level="NONE",
            reasons=["No matching opportunity in catalog"],
            is_candidate_only=False,
            details="New canonical opportunity candidate",
        )
