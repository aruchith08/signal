"""
Unit Tests for AIVerificationService & AIUsagePolicy
"""
import unittest
from services.verification.ai_verification import AIVerificationService
from services.intelligence.usage_policy import AIUsagePolicy


class TestAIVerificationService(unittest.TestCase):
    def setUp(self):
        self.service = AIVerificationService()

    async def async_test_verify_merge_decision(self):
        opp_a = {
            "title": "TCS CodeVita Season 13",
            "organization_name": "Tata Consultancy Services",
            "year": 2026,
            "category": "competitive_programming",
        }
        opp_b = {
            "title": "CodeVita 2026",
            "organization_name": "Tata Consultancy Services",
            "year": 2026,
            "category": "competitive_programming",
        }
        res = await self.service.verify_pair(opp_a, opp_b)
        self.assertTrue(res.same_opportunity)
        self.assertEqual(res.recommended_action, "MERGE")
        self.assertGreaterEqual(res.confidence, 0.90)

    async def async_test_verify_different_org(self):
        opp_a = {"title": "TCS CodeVita", "organization_name": "TCS", "year": 2026}
        opp_b = {"title": "Google Code Jam", "organization_name": "Google", "year": 2026}
        res = await self.service.verify_pair(opp_a, opp_b)
        self.assertFalse(res.same_opportunity)
        self.assertEqual(res.recommended_action, "KEEP_SEPARATE")

    def test_verify_pair_sync(self):
        import asyncio
        asyncio.run(self.async_test_verify_merge_decision())
        asyncio.run(self.async_test_verify_different_org())

    def test_usage_policy_rate_limiting(self):
        policy = AIUsagePolicy(max_verification_calls_per_run=2)
        self.assertTrue(policy.can_call_verification())
        policy.record_call("verification", "mock", 10.0, True)
        self.assertTrue(policy.can_call_verification())
        policy.record_call("verification", "mock", 10.0, True)
        self.assertFalse(policy.can_call_verification())
        self.assertEqual(policy.verification_calls_remaining, 0)


if __name__ == "__main__":
    unittest.main()
