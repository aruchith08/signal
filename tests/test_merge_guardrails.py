"""
Unit Tests for MergeGuardrails
"""
import unittest
from services.verification.merge_guardrails import MergeGuardrails
from shared.constants import MergeRejectionReason


class TestMergeGuardrails(unittest.TestCase):
    def test_allow_compatible_records(self):
        rec_a = {
            "organization_name": "Tata Consultancy Services",
            "year": 2026,
            "season": "Season 13",
            "category": "competitive_programming",
        }
        rec_b = {
            "organization_name": "Tata Consultancy Services",
            "year": 2026,
            "season": "Season 13",
            "category": "competitive_programming",
        }
        decision = MergeGuardrails.evaluate(rec_a, rec_b)
        self.assertTrue(decision.allowed)
        self.assertIsNone(decision.reason)

    def test_reject_organization_conflict(self):
        rec_a = {"organization_name": "TCS", "year": 2026}
        rec_b = {"organization_name": "Google", "year": 2026}
        decision = MergeGuardrails.evaluate(rec_a, rec_b)
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, MergeRejectionReason.ORGANIZATION_CONFLICT.value)

    def test_reject_year_conflict(self):
        rec_a = {"organization_name": "TCS", "year": 2025}
        rec_b = {"organization_name": "TCS", "year": 2026}
        decision = MergeGuardrails.evaluate(rec_a, rec_b)
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, MergeRejectionReason.YEAR_CONFLICT.value)

    def test_reject_season_conflict(self):
        rec_a = {"organization_name": "TCS", "year": 2026, "season": "Season 12"}
        rec_b = {"organization_name": "TCS", "year": 2026, "season": "Season 13"}
        decision = MergeGuardrails.evaluate(rec_a, rec_b)
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, MergeRejectionReason.SEASON_CONFLICT.value)

    def test_reject_incompatible_category_conflict(self):
        rec_a = {"organization_name": "AICTE", "category": "government"}
        rec_b = {"organization_name": "AICTE", "category": "competitive_programming"}
        decision = MergeGuardrails.evaluate(rec_a, rec_b)
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, MergeRejectionReason.CATEGORY_CONFLICT.value)


if __name__ == "__main__":
    unittest.main()
