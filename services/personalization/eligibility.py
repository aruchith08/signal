"""
Eligibility Evaluator — Conservative evaluation of user academic compatibility
"""
import re
from typing import Optional, Dict, Any, Tuple
from shared.constants import EligibilityStatus


class EligibilityEvaluator:
    """
    Evaluates compatibility between a user's academic profile and an opportunity's eligibility constraints.

    Conservative Principles:
    - Never falsely claim ELIGIBLE or INELIGIBLE.
    - If criteria are sparse or open to all, return LIKELY_ELIGIBLE or UNKNOWN.
    - Explicit exclusions (e.g. 'Only PhD', 'Only 2025 graduates') yield INELIGIBLE.
    """

    DEGREE_GROUPS = {
        "undergraduate": ["b.tech", "b.e", "btech", "be", "bca", "bsc", "b.sc", "undergraduate", "ug", "bachelor"],
        "postgraduate": ["m.tech", "mtech", "me", "m.e", "mca", "msc", "m.sc", "postgraduate", "pg", "master"],
        "doctoral": ["phd", "ph.d", "doctorate", "doctoral", "research scholar"],
    }

    @classmethod
    def evaluate(
        cls,
        user_profile: Optional[Dict[str, Any]],
        opportunity_eligibility: Optional[str],
        opportunity_target_audience: Optional[str] = None,
        opportunity_title: Optional[str] = None,
    ) -> Tuple[EligibilityStatus, Optional[str]]:
        """
        Evaluate eligibility given user profile and opportunity constraints.
        Returns (EligibilityStatus, explanation_reason).
        """
        if not user_profile:
            return EligibilityStatus.UNKNOWN, "No user profile available for eligibility evaluation"

        eligibility_text = (opportunity_eligibility or "").strip().lower()
        audience_text = (opportunity_target_audience or "").strip().lower()
        title_text = (opportunity_title or "").strip().lower()
        combined_text = f"{title_text} {eligibility_text} {audience_text}".strip()

        if not combined_text or combined_text in ["open to all", "all students", "anyone", "students, developers, innovators"]:
            return EligibilityStatus.LIKELY_ELIGIBLE, "Open to all students and developers"

        user_degree = (user_profile.get("degree") or "").strip().lower()
        user_level = (user_profile.get("education_level") or "").strip().lower()
        user_grad_year = user_profile.get("graduation_year")
        user_current_year = user_profile.get("current_year")
        user_branch = (user_profile.get("branch") or "").strip().lower()

        # 1. Degree / Level Level Checks
        is_user_ug = any(d in user_degree for d in cls.DEGREE_GROUPS["undergraduate"]) or "undergraduate" in user_level or "bachelor" in user_level
        is_user_pg = any(d in user_degree for d in cls.DEGREE_GROUPS["postgraduate"]) or "postgraduate" in user_level or "master" in user_level
        is_user_doc = any(d in user_degree for d in cls.DEGREE_GROUPS["doctoral"]) or "phd" in user_level

        # Check explicit exclusions
        if re.search(r"\b(only\s+ph\.?d|ph\.?d\s+candidates\s+only|doctoral\s+only)\b", combined_text):
            if is_user_ug and not is_user_doc:
                return EligibilityStatus.INELIGIBLE, "Restricted to PhD / doctoral candidates"

        if re.search(r"\b(only\s+postgraduates?|masters?\s+only|m\.?tech\s+only|mca\s+only)\b", combined_text):
            if is_user_ug and not is_user_pg:
                return EligibilityStatus.INELIGIBLE, "Restricted to postgraduate / master's students"

        if re.search(r"\b(only\s+undergraduates?|b\.?tech\s+only|b\.e\.?\s+only|bachelors?\s+only)\b", combined_text):
            if is_user_doc or (is_user_pg and not is_user_ug):
                return EligibilityStatus.INELIGIBLE, "Restricted to undergraduate students"

        # Check explicit inclusions
        if is_user_ug and re.search(r"\b(undergraduate|b\.?tech|b\.e\.?|bachelor|bca|engineering\s+students?)\b", combined_text):
            return EligibilityStatus.ELIGIBLE, "Eligible: Matches undergraduate / engineering requirements"

        if is_user_pg and re.search(r"\b(postgraduate|m\.?tech|mca|master|m\.?sc)\b", combined_text):
            return EligibilityStatus.ELIGIBLE, "Eligible: Matches postgraduate requirements"

        # 2. Graduation Year Checks
        if user_grad_year:
            year_str = str(user_grad_year)
            # Check if specific graduation years are mentioned
            grad_matches = re.findall(r"\b(202[4-9]|203[0-5])\s*(?:batch|passout|graduat(?:es?|ing))\b", combined_text)
            if grad_matches:
                if year_str in grad_matches:
                    return EligibilityStatus.ELIGIBLE, f"Eligible: Matches required graduation year ({year_str})"
                else:
                    return EligibilityStatus.INELIGIBLE, f"Ineligible: Requires graduation batch {', '.join(grad_matches)}"

        # 3. Current Year Checks
        if user_current_year:
            year_word = {1: "1st", 2: "2nd", 3: "3rd", 4: "4th"}.get(user_current_year, f"{user_current_year}th")
            if re.search(rf"\b(final\s+year|{year_word}\s+year)\b", combined_text):
                if user_current_year == 4 and "final year" in combined_text:
                    return EligibilityStatus.ELIGIBLE, "Eligible: Matches final year requirement"
                if f"{year_word} year" in combined_text:
                    return EligibilityStatus.ELIGIBLE, f"Eligible: Matches {year_word} year requirement"

        # Default fallback
        if "student" in combined_text or "developer" in combined_text or "college" in combined_text:
            return EligibilityStatus.LIKELY_ELIGIBLE, "Likely eligible based on student/developer audience"

        return EligibilityStatus.UNKNOWN, "Eligibility criteria could not be definitively determined"
