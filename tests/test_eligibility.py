"""
Tests for EligibilityEvaluator — Academic compatibility and conservative handling
"""
import unittest
from services.personalization.eligibility import EligibilityEvaluator
from shared.constants import EligibilityStatus


class TestEligibilityEvaluator(unittest.TestCase):

    def test_missing_profile_returns_unknown(self):
        status, reason = EligibilityEvaluator.evaluate(
            user_profile=None,
            opportunity_eligibility="Open to undergraduate students",
        )
        self.assertEqual(status, EligibilityStatus.UNKNOWN)

    def test_open_to_all_returns_likely_eligible(self):
        profile = {"degree": "B.Tech", "education_level": "Undergraduate"}
        status, reason = EligibilityEvaluator.evaluate(
            user_profile=profile,
            opportunity_eligibility="Open to all students and developers",
        )
        self.assertEqual(status, EligibilityStatus.LIKELY_ELIGIBLE)

    def test_undergraduate_matching(self):
        profile = {"degree": "B.Tech", "education_level": "Undergraduate", "branch": "Computer Science"}
        status, reason = EligibilityEvaluator.evaluate(
            user_profile=profile,
            opportunity_eligibility="Eligibility: Open to all undergraduate engineering students",
        )
        self.assertEqual(status, EligibilityStatus.ELIGIBLE)
        self.assertIn("undergraduate", reason.lower())

    def test_undergraduate_vs_phd_only_ineligible(self):
        profile = {"degree": "B.Tech", "education_level": "Undergraduate"}
        status, reason = EligibilityEvaluator.evaluate(
            user_profile=profile,
            opportunity_eligibility="Only PhD candidates are eligible to submit research papers",
        )
        self.assertEqual(status, EligibilityStatus.INELIGIBLE)
        self.assertIn("phd", reason.lower())

    def test_undergraduate_vs_masters_only_ineligible(self):
        profile = {"degree": "B.Tech", "education_level": "Undergraduate"}
        status, reason = EligibilityEvaluator.evaluate(
            user_profile=profile,
            opportunity_eligibility="Only postgraduates and M.Tech students may apply",
        )
        self.assertEqual(status, EligibilityStatus.INELIGIBLE)
        self.assertIn("postgraduate", reason.lower())

    def test_postgraduate_vs_undergraduate_only_ineligible(self):
        profile = {"degree": "PhD", "education_level": "Doctoral"}
        status, reason = EligibilityEvaluator.evaluate(
            user_profile=profile,
            opportunity_eligibility="Only undergraduates or B.Tech only",
        )
        self.assertEqual(status, EligibilityStatus.INELIGIBLE)

    def test_graduation_year_matching(self):
        profile = {"degree": "B.Tech", "graduation_year": 2026}
        # Matching batch
        status, reason = EligibilityEvaluator.evaluate(
            user_profile=profile,
            opportunity_eligibility="Open for 2026 batch graduates only",
        )
        self.assertEqual(status, EligibilityStatus.ELIGIBLE)

        # Ineligible batch
        status, reason = EligibilityEvaluator.evaluate(
            user_profile=profile,
            opportunity_eligibility="Hiring for 2024 batch and 2025 batch passouts only",
        )
        self.assertEqual(status, EligibilityStatus.INELIGIBLE)

    def test_current_year_matching(self):
        profile = {"degree": "B.Tech", "current_year": 2}
        status, reason = EligibilityEvaluator.evaluate(
            user_profile=profile,
            opportunity_eligibility="Exclusively for 2nd year students",
        )
        self.assertEqual(status, EligibilityStatus.ELIGIBLE)

    def test_unspecified_criteria_returns_unknown(self):
        profile = {"degree": "B.Tech", "education_level": "Undergraduate"}
        status, reason = EligibilityEvaluator.evaluate(
            user_profile=profile,
            opportunity_eligibility="Selected finalists will be invited to the regional rounds.",
        )
        self.assertEqual(status, EligibilityStatus.UNKNOWN)


if __name__ == "__main__":
    unittest.main()
