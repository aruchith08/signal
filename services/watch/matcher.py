"""
Program Watch Matcher — Deterministic, explainable matching for monitored programs
Evaluates incoming discoveries against ProgramWatch rules (Alias, Canonical Name, Name, Keywords, Source Association)
with strict false-positive guardrails.
"""
from dataclasses import dataclass, field
import logging
import re
from typing import List, Optional, Set, Tuple

from apps.api.models.discovery import RawDiscovery
from apps.api.models.program_watch import (
    ProgramWatch,
    ProgramWatchAlias,
    ProgramWatchKeyword,
    ProgramWatchSource,
)
from shared.constants import WatchConfidence, WatchMatchLevel
from shared.utils import canonicalize_url, normalize_title

logger = logging.getLogger("signal.watch.matcher")


@dataclass
class WatchMatchResult:
    """Structured, explainable evaluation result for a ProgramWatch against a RawDiscovery."""
    matched: bool
    score: float = 0.0
    match_level: Optional[WatchMatchLevel] = None
    match_reason: str = ""
    matched_terms: List[str] = field(default_factory=list)
    confidence: WatchConfidence = WatchConfidence.LOW


class ProgramWatchMatcher:
    """
    Deterministic rule-based matcher for monitored programs.
    Evaluates:
      1. Exact Alias
      2. Exact Canonical Name
      3. Exact Program Name
      4. Weighted Distinctive Keywords (with false-positive protection)
      5. Source Association (as supporting evidence)
    """

    @staticmethod
    def _search_word(term: str, text: str) -> bool:
        """Check for exact whole-word or phrase boundary in text."""
        if not term or not text:
            return False
        escaped = re.escape(term.strip().lower())
        pattern = rf"\b{escaped}\b"
        return bool(re.search(pattern, text.lower()))

    @classmethod
    def match(
        cls,
        discovery: RawDiscovery,
        watch: ProgramWatch,
    ) -> WatchMatchResult:
        """
        Evaluate a RawDiscovery against a ProgramWatch.
        Returns a structured WatchMatchResult with explainability terms.
        """
        if not watch.is_active:
            return WatchMatchResult(
                matched=False,
                score=0.0,
                match_reason=f"Watch '{watch.name}' is inactive",
                confidence=WatchConfidence.LOW,
            )

        title = discovery.raw_title or ""
        content = discovery.raw_content or ""
        norm_title = normalize_title(title)
        norm_content = normalize_title(content)

        # -------------------------------------------------------------
        # Rule 1: Exact Alias Match
        # -------------------------------------------------------------
        for alias in watch.aliases:
            alias_clean = alias.alias.strip()
            norm_alias = alias.normalized_alias.strip()

            # Check in raw title and normalized title
            in_title = cls._search_word(alias_clean, title) or cls._search_word(norm_alias, norm_title)
            if in_title:
                return WatchMatchResult(
                    matched=True,
                    score=1.0,
                    match_level=WatchMatchLevel.EXACT_ALIAS,
                    match_reason=f"Exact alias '{alias_clean}' found in title",
                    matched_terms=[alias_clean],
                    confidence=WatchConfidence.HIGH,
                )

            # Check in content (high confidence, but slightly below title)
            in_content = cls._search_word(alias_clean, content) or cls._search_word(norm_alias, norm_content)
            if in_content:
                return WatchMatchResult(
                    matched=True,
                    score=0.92,
                    match_level=WatchMatchLevel.EXACT_ALIAS,
                    match_reason=f"Exact alias '{alias_clean}' found in announcement content",
                    matched_terms=[alias_clean],
                    confidence=WatchConfidence.HIGH,
                )

        # -------------------------------------------------------------
        # Rule 2: Exact Name Match
        # -------------------------------------------------------------
        name = watch.name.strip()
        norm_name = normalize_title(name)
        if cls._search_word(name, title) or cls._search_word(norm_name, norm_title):
            return WatchMatchResult(
                matched=True,
                score=0.95,
                match_level=WatchMatchLevel.EXACT_NAME,
                match_reason=f"Exact program name '{name}' found in title",
                matched_terms=[name],
                confidence=WatchConfidence.HIGH,
            )

        # -------------------------------------------------------------
        # Rule 3: Exact Canonical Name Match
        # -------------------------------------------------------------
        if watch.canonical_name:
            canon = watch.canonical_name.strip()
            norm_canon = normalize_title(canon)

            if cls._search_word(canon, title) or cls._search_word(norm_canon, norm_title):
                return WatchMatchResult(
                    matched=True,
                    score=0.95,
                    match_level=WatchMatchLevel.EXACT_CANONICAL_NAME,
                    match_reason=f"Exact canonical name '{canon}' found in title",
                    matched_terms=[canon],
                    confidence=WatchConfidence.HIGH,
                )

        # -------------------------------------------------------------
        # Rule 4: Weighted Keywords with False-Positive Guardrails
        # -------------------------------------------------------------
        # Guardrail requirement: Generic keywords like "programming", "competition",
        # "hackathon", "challenge" ALONE must NEVER trigger a match.
        # At least ONE distinctive keyword must match.
        matched_distinctive_terms: List[str] = []
        matched_generic_terms: List[str] = []
        distinctive_score: float = 0.0
        generic_score: float = 0.0

        for kw in watch.keywords:
            kw_clean = kw.keyword.strip()
            norm_kw = kw.normalized_keyword.strip()

            found_in_title = cls._search_word(kw_clean, title) or cls._search_word(norm_kw, norm_title)
            found_in_content = cls._search_word(kw_clean, content) or cls._search_word(norm_kw, norm_content)

            if found_in_title or found_in_content:
                multiplier = 1.0 if found_in_title else 0.5
                term_weight = kw.weight * multiplier

                if kw.is_distinctive:
                    matched_distinctive_terms.append(kw_clean)
                    distinctive_score += term_weight
                else:
                    matched_generic_terms.append(kw_clean)
                    generic_score += term_weight

        # Check Source Association as supporting evidence
        source_matched = False
        source_reason = ""
        for src in watch.sources:
            if not src.is_active:
                continue
            if src.source_id and discovery.source_id == src.source_id:
                source_matched = True
                source_reason = "associated source"
                break
            if src.url and discovery.canonical_url and src.url in discovery.canonical_url:
                source_matched = True
                source_reason = f"matching source URL ({src.url})"
                break

        # Source support bonus (supporting evidence only, up to +0.15)
        source_bonus = 0.15 if source_matched else 0.0

        # GUARDRAIL EVALUATION:
        # If no distinctive keyword matched, reject keyword combination match!
        if matched_distinctive_terms:
            total_kw_score = min(distinctive_score + (generic_score * 0.5) + source_bonus, 1.0)
            all_terms = matched_distinctive_terms + matched_generic_terms

            if total_kw_score >= 0.60:
                confidence = WatchConfidence.HIGH if total_kw_score >= 0.90 else WatchConfidence.MEDIUM
                reason = f"Distinctive keywords matched: {', '.join(matched_distinctive_terms)}"
                if matched_generic_terms:
                    reason += f" alongside {', '.join(matched_generic_terms)}"
                if source_matched:
                    reason += f" from {source_reason}"

                return WatchMatchResult(
                    matched=True,
                    score=round(total_kw_score, 2),
                    match_level=WatchMatchLevel.KEYWORD_COMBINATION,
                    match_reason=reason,
                    matched_terms=all_terms,
                    confidence=confidence,
                )

        # Source association alone without distinctive keywords is NOT sufficient
        if source_matched and generic_score > 0:
            logger.debug(
                f"[WatchMatcher] Source matched but rejected due to lack of distinctive keywords for watch '{watch.name}'"
            )

        # No qualified match
        return WatchMatchResult(
            matched=False,
            score=round(distinctive_score + (generic_score * 0.2), 2),
            match_reason="No distinctive alias, canonical name, or distinctive keywords matched",
            matched_terms=matched_distinctive_terms + matched_generic_terms,
            confidence=WatchConfidence.LOW,
        )
