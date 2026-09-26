"""
Relevance Scoring Engine — Deterministic 0-100 score evaluation
"""
import re
from typing import Dict, List, Optional, Tuple, Any
from shared.constants import EligibilityStatus, PriorityLevel


class RelevanceScorer:
    """
    Computes a deterministic, explainable relevance score (0 - 100)
    evaluating an opportunity against a user's intelligence profile.
    """

    @classmethod
    def calculate(
        cls,
        opportunity_data: Dict[str, Any],
        user_interests: List[Dict[str, Any]],
        user_skills: List[str],
        user_preferred_types: List[str],
        eligibility_status: EligibilityStatus,
        program_watch_matches: List[Dict[str, Any]],
    ) -> Tuple[int, float, Dict[str, float], List[str], List[str], List[str]]:
        """
        Calculates the score and extracts matching evidence.

        Returns:
            (total_score, confidence, component_scores, matched_interests, matched_skills, matched_programs)
        """
        component_scores: Dict[str, float] = {
            "interest_match": 0.0,
            "category_match": 0.0,
            "skill_match": 0.0,
            "academic_eligibility": 0.0,
            "program_watch_match": 0.0,
            "opportunity_priority": 0.0,
        }

        opp_category = (opportunity_data.get("category") or "").strip().lower()
        opp_title = (opportunity_data.get("title") or "").strip().lower()
        opp_summary = (opportunity_data.get("summary") or "").strip().lower()
        opp_tags = (opportunity_data.get("tags") or "").strip().lower()
        opp_skills = (opportunity_data.get("required_skills") or "").strip().lower()
        opp_priority = (opportunity_data.get("priority") or "medium").strip().lower()

        searchable_text = f"{opp_title} {opp_category} {opp_tags} {opp_skills} {opp_summary}"

        # 1. Interest Match (0 – 30)
        matched_interests: List[str] = []
        max_interest_score = 0.0

        for interest in user_interests:
            cat = (interest.get("category") or "").strip().lower()
            tag = (interest.get("tag") or "").strip().lower()
            weight = float(interest.get("weight", 1.0))

            # Match on category or tag
            is_match = False
            if cat and (cat == opp_category or cat in opp_category or opp_category in cat):
                is_match = True
            elif tag and (tag in searchable_text or tag.replace("_", " ") in searchable_text):
                is_match = True

            if is_match:
                matched_name = tag or cat
                if matched_name not in matched_interests:
                    matched_interests.append(matched_name)
                # Score component: weight * 30
                score_contrib = weight * 30.0
                if score_contrib > max_interest_score:
                    max_interest_score = score_contrib

        component_scores["interest_match"] = round(min(30.0, max_interest_score), 1)

        # 2. Category Match (0 – 15)
        category_score = 0.0
        if user_preferred_types:
            norm_preferred = [p.strip().lower() for p in user_preferred_types if p]
            if any(p == opp_category or p in opp_category or opp_category in p for p in norm_preferred):
                category_score = 15.0
            else:
                category_score = 5.0
        else:
            # Fallback based on interest match
            category_score = 15.0 if component_scores["interest_match"] >= 20.0 else (
                10.0 if component_scores["interest_match"] > 0 else 5.0
            )
        component_scores["category_match"] = round(category_score, 1)

        # 3. Skill Match (0 – 15)
        matched_skills: List[str] = []
        for skill in user_skills:
            clean_skill = skill.strip().lower()
            if not clean_skill:
                continue
            # Word boundary regex for short skills like 'c', 'r', 'go' vs 'python'
            pattern = rf"\b{re.escape(clean_skill)}\b" if len(clean_skill) <= 3 else re.escape(clean_skill)
            if re.search(pattern, searchable_text):
                matched_skills.append(clean_skill)

        if len(matched_skills) >= 2:
            skill_score = 15.0
        elif len(matched_skills) == 1:
            skill_score = 10.0
        else:
            skill_score = 0.0
        component_scores["skill_match"] = skill_score

        # 4. Academic Eligibility (0 – 15)
        eligibility_score_map = {
            EligibilityStatus.ELIGIBLE: 15.0,
            EligibilityStatus.LIKELY_ELIGIBLE: 10.0,
            EligibilityStatus.UNKNOWN: 5.0,
            EligibilityStatus.LIKELY_INELIGIBLE: 2.0,
            EligibilityStatus.INELIGIBLE: 0.0,
        }
        component_scores["academic_eligibility"] = eligibility_score_map.get(eligibility_status, 5.0)

        # 5. Program Watch Match (0 – 15)
        matched_programs: List[str] = []
        watch_score = 0.0
        if program_watch_matches:
            best_match_score = 0.0
            for wm in program_watch_matches:
                score = float(wm.get("match_score", 0.0))
                prog_name = wm.get("program_name") or "Watched Program"
                if prog_name not in matched_programs:
                    matched_programs.append(prog_name)
                if score > best_match_score:
                    best_match_score = score
            watch_score = min(15.0, best_match_score * 15.0)
        component_scores["program_watch_match"] = round(watch_score, 1)

        # 6. Opportunity Priority (0 – 10)
        priority_map = {
            "critical": 10.0,
            "high": 7.0,
            "medium": 4.0,
            "low": 1.0,
        }
        component_scores["opportunity_priority"] = priority_map.get(opp_priority, 4.0)

        raw_total = sum(component_scores.values())

        # If user is strictly INELIGIBLE, cap score to prevent accidental alert spam
        if eligibility_status == EligibilityStatus.INELIGIBLE:
            total_score = int(min(25, raw_total))
        else:
            total_score = int(min(100, max(0, round(raw_total))))

        # Confidence is higher when we have more concrete signals (interests, skills, watches)
        signals_present = (
            (1 if matched_interests else 0) +
            (1 if matched_skills else 0) +
            (1 if matched_programs else 0) +
            (1 if eligibility_status in [EligibilityStatus.ELIGIBLE, EligibilityStatus.INELIGIBLE] else 0)
        )
        confidence = min(0.98, max(0.50, 0.50 + (signals_present * 0.12)))

        return total_score, confidence, component_scores, matched_interests, matched_skills, matched_programs
