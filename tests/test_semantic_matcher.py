"""
Unit Tests for SemanticMatcher
"""
import unittest
from services.verification.semantic_matcher import SemanticMatcher, MockEmbeddingProvider, cosine_similarity


class TestSemanticMatcher(unittest.TestCase):
    def setUp(self):
        self.matcher = SemanticMatcher()

    async def async_test_similarity(self):
        text_a = self.matcher.build_invariant_text(
            title="TCS CodeVita Season 13",
            organization_name="Tata Consultancy Services",
            category="competitive_programming",
            year=2026,
            summary="Global competitive programming competition for engineering students.",
        )
        text_b = self.matcher.build_invariant_text(
            title="TCS CodeVita 2026",
            organization_name="Tata Consultancy Services",
            category="competitive_programming",
            year=2026,
            summary="Programming contest for engineering students by TCS.",
        )
        text_c = self.matcher.build_invariant_text(
            title="Smart India Hackathon",
            organization_name="Ministry of Education",
            category="hackathon",
            year=2026,
            summary="Nationwide digital product building hackathon.",
        )

        sim_ab = await self.matcher.compute_similarity(text_a, text_b)
        sim_ac = await self.matcher.compute_similarity(text_a, text_c)

        self.assertGreater(sim_ab, 0.70, f"Expected high similarity between related CodeVita texts, got {sim_ab}")
        self.assertGreater(sim_ab, sim_ac, f"CodeVita-to-CodeVita ({sim_ab}) should exceed CodeVita-to-SIH ({sim_ac})")

    def test_similarity_sync(self):
        import asyncio
        asyncio.run(self.async_test_similarity())

    def test_invariant_text_strips_dates(self):
        raw_summary = "Registration ends on 25/09/2026 at https://codevita.tcs.com/apply. Top performers win cash."
        text = self.matcher.build_invariant_text(title="CodeVita", summary=raw_summary)
        self.assertNotIn("https://", text)
        self.assertIn("Top performers win cash", text)


if __name__ == "__main__":
    unittest.main()
