"""
Merge Guardrails — Strict false-merge prevention system
Ensures records from different organizations, conflicting years, conflicting seasons,
or incompatible categories are NEVER merged automatically.
"""
from typing import Any, Dict, Optional
from pydantic import BaseModel
from shared.constants import MergeRejectionReason


class MergeDecision(BaseModel):
    """Structured decision returned by merge guardrails."""
    allowed: bool
    reason: Optional[str] = None
    details: str = ""


class MergeGuardrails:
    """Evaluates whether two opportunity records can safely be merged."""

    @staticmethod
    def evaluate(
        record_a: Dict[str, Any],
        record_b: Dict[str, Any],
    ) -> MergeDecision:
        """
        Inspect fields from record_a and record_b.
        Record dictionaries can contain:
        - organization_id / organization_name
        - year
        - season
        - category
        - title / canonical_name
        """
        # 1. Organization Conflict Guardrail
        org_a = str(record_a.get("organization_id") or record_a.get("organization_name") or "").strip().lower()
        org_b = str(record_b.get("organization_id") or record_b.get("organization_name") or "").strip().lower()

        if org_a and org_b and org_a != org_b:
            return MergeDecision(
                allowed=False,
                reason=MergeRejectionReason.ORGANIZATION_CONFLICT.value,
                details=f"Conflicting organizations: '{org_a}' vs '{org_b}'",
            )

        # 2. Year Conflict Guardrail
        year_a = record_a.get("year")
        year_b = record_b.get("year")

        if year_a and year_b:
            try:
                y_a = int(year_a)
                y_b = int(year_b)
                if y_a != y_b:
                    return MergeDecision(
                        allowed=False,
                        reason=MergeRejectionReason.YEAR_CONFLICT.value,
                        details=f"Conflicting opportunity years: {y_a} vs {y_b}",
                    )
            except (ValueError, TypeError):
                pass

        # 3. Season Conflict Guardrail (e.g. Season 12 vs Season 13, Summer vs Winter)
        season_a = str(record_a.get("season") or "").strip().lower()
        season_b = str(record_b.get("season") or "").strip().lower()

        if season_a and season_b and season_a != season_b:
            return MergeDecision(
                allowed=False,
                reason=MergeRejectionReason.SEASON_CONFLICT.value,
                details=f"Conflicting seasons: '{season_a}' vs '{season_b}'",
            )

        # 4. Incompatible Category Conflict
        cat_a = str(record_a.get("category") or "").strip().lower()
        cat_b = str(record_b.get("category") or "").strip().lower()

        # Certain categories are strictly incompatible (e.g., government grant vs competitive programming)
        if cat_a and cat_b and cat_a != "other" and cat_b != "other":
            strictly_incompatible_pairs = [
                ("government", "competitive_programming"),
                ("scholarship_fellowship", "hackathon"),
            ]
            for c1, c2 in strictly_incompatible_pairs:
                if (cat_a == c1 and cat_b == c2) or (cat_a == c2 and cat_b == c1):
                    return MergeDecision(
                        allowed=False,
                        reason=MergeRejectionReason.CATEGORY_CONFLICT.value,
                        details=f"Incompatible categories: '{cat_a}' vs '{cat_b}'",
                    )

        return MergeDecision(
            allowed=True,
            reason=None,
            details="All guardrails passed: no organization, year, season, or category conflicts detected",
        )
