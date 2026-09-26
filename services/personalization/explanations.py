"""
Relevance Result and Explanation Generator
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from shared.constants import EligibilityStatus


@dataclass
class RelevanceResult:
    """Structured explainable relevance result."""
    score: int
    confidence: float
    eligibility_status: EligibilityStatus
    reasons: List[str] = field(default_factory=list)
    matched_interests: List[str] = field(default_factory=list)
    matched_skills: List[str] = field(default_factory=list)
    matched_programs: List[str] = field(default_factory=list)
    component_scores: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "score": self.score,
            "confidence": round(self.confidence, 2),
            "eligibility_status": self.eligibility_status.value,
            "reasons": self.reasons,
            "matched_interests": self.matched_interests,
            "matched_skills": self.matched_skills,
            "matched_programs": self.matched_programs,
            "component_scores": {k: round(v, 1) for k, v in self.component_scores.items()},
        }


class ExplanationGenerator:
    """Generates concise, human-readable explanations of why an opportunity is relevant."""

    @staticmethod
    def generate(
        component_scores: Dict[str, float],
        matched_interests: List[str],
        matched_skills: List[str],
        matched_programs: List[str],
        eligibility_status: EligibilityStatus,
        eligibility_reason: Optional[str] = None,
        priority: Optional[str] = None,
    ) -> List[str]:
        reasons: List[str] = []

        # 1. Program Watch
        if matched_programs:
            for prog in matched_programs:
                reasons.append(f"Program Watch hit: '{prog}' is an actively monitored program")

        # 2. Interests
        if matched_interests:
            for interest in matched_interests[:3]:
                reasons.append(f"Matches your interest in {interest.replace('_', ' ').title()}")

        # 3. Skills
        if matched_skills:
            skill_list = ", ".join(s.title() for s in matched_skills[:3])
            reasons.append(f"Matches your skills: {skill_list}")

        # 4. Priority
        if priority and priority.lower() == "critical":
            reasons.append("Opportunity priority is CRITICAL")
        elif priority and priority.lower() == "high":
            reasons.append("High-priority flagship opportunity")

        # 5. Eligibility
        if eligibility_status == EligibilityStatus.ELIGIBLE and eligibility_reason:
            reasons.append(eligibility_reason)
        elif eligibility_status == EligibilityStatus.INELIGIBLE and eligibility_reason:
            reasons.append(f"Warning: {eligibility_reason}")

        if not reasons:
            reasons.append("General opportunity matching default discoverability criteria")

        return reasons
