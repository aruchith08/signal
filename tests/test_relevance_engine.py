"""
Tests for RelevanceScorer and ExplanationGenerator
"""
import unittest
from services.personalization.scoring import RelevanceScorer
from services.personalization.explanations import ExplanationGenerator
from shared.constants import EligibilityStatus


class TestRelevanceScoring(unittest.TestCase):

    def setUp(self):
        self.user_interests = [
            {"category": "competitive_programming", "tag": "competitive_programming", "weight": 1.0},
            {"category": "ai_ml", "tag": "machine_learning", "weight": 0.8},
            {"category": "hackathons", "tag": "hackathons", "weight": 0.9},
        ]
        self.user_skills = ["python", "c++", "algorithms"]
        self.user_preferred_types = ["competitive_programming", "hackathon"]

    def test_high_relevance_for_matching_interest_and_skills(self):
        opportunity = {
            "title": "CodeChef Starters 150 Contest",
            "category": "competitive_programming",
            "summary": "Compete in algorithmic challenges using Python, C++, or Java.",
            "tags": "competitive_programming, algorithms",
            "required_skills": "python, c++",
            "priority": "high",
        }
        score, confidence, component_scores, matched_interests, matched_skills, matched_programs = (
            RelevanceScorer.calculate(
                opportunity_data=opportunity,
                user_interests=self.user_interests,
                user_skills=self.user_skills,
                user_preferred_types=self.user_preferred_types,
                eligibility_status=EligibilityStatus.ELIGIBLE,
                program_watch_matches=[],
            )
        )
        self.assertGreaterEqual(score, 80)
        self.assertEqual(component_scores["interest_match"], 30.0)
        self.assertEqual(component_scores["category_match"], 15.0)
        self.assertEqual(component_scores["skill_match"], 15.0)
        self.assertEqual(component_scores["academic_eligibility"], 15.0)
        self.assertEqual(component_scores["opportunity_priority"], 7.0)
        self.assertIn("competitive_programming", matched_interests)
        self.assertIn("python", matched_skills)

    def test_program_watch_match_boosts_score(self):
        opportunity = {
            "title": "TCS CodeVita Season 13",
            "category": "competitive_programming",
            "summary": "Flagship global coding competition.",
            "tags": "competitive_programming",
            "required_skills": "algorithms",
            "priority": "critical",
        }
        watch_matches = [{"program_name": "TCS CodeVita", "match_score": 1.0}]

        score, confidence, component_scores, _, _, matched_programs = RelevanceScorer.calculate(
            opportunity_data=opportunity,
            user_interests=self.user_interests,
            user_skills=self.user_skills,
            user_preferred_types=self.user_preferred_types,
            eligibility_status=EligibilityStatus.ELIGIBLE,
            program_watch_matches=watch_matches,
        )
        self.assertGreaterEqual(score, 90)
        self.assertEqual(component_scores["program_watch_match"], 15.0)
        self.assertEqual(component_scores["opportunity_priority"], 10.0)
        self.assertIn("TCS CodeVita", matched_programs)

    def test_unrelated_opportunity_receives_low_score(self):
        opportunity = {
            "title": "National Classical Literature Fellowship",
            "category": "education_research",
            "summary": "Grant for ancient Sanskrit manuscripts translation.",
            "tags": "history, literature, humanities",
            "required_skills": "translation, sanskrit",
            "priority": "low",
        }
        score, confidence, component_scores, matched_interests, matched_skills, _ = RelevanceScorer.calculate(
            opportunity_data=opportunity,
            user_interests=self.user_interests,
            user_skills=self.user_skills,
            user_preferred_types=self.user_preferred_types,
            eligibility_status=EligibilityStatus.UNKNOWN,
            program_watch_matches=[],
        )
        self.assertLess(score, 40)
        self.assertEqual(len(matched_interests), 0)
        self.assertEqual(len(matched_skills), 0)

    def test_ineligible_opportunity_score_is_capped(self):
        opportunity = {
            "title": "Doctoral AI Research Fellowship",
            "category": "ai_ml",
            "summary": "PhD stipend for machine learning researchers using python.",
            "tags": "ai_ml, machine_learning",
            "required_skills": "python",
            "priority": "high",
        }
        score, confidence, component_scores, _, _, _ = RelevanceScorer.calculate(
            opportunity_data=opportunity,
            user_interests=self.user_interests,
            user_skills=self.user_skills,
            user_preferred_types=self.user_preferred_types,
            eligibility_status=EligibilityStatus.INELIGIBLE,
            program_watch_matches=[],
        )
        # Even with high interest and skills, strictly capped for ineligible
        self.assertLessEqual(score, 25)

    def test_explanation_generation(self):
        reasons = ExplanationGenerator.generate(
            component_scores={"interest_match": 30.0, "skill_match": 15.0, "program_watch_match": 15.0},
            matched_interests=["competitive_programming"],
            matched_skills=["python", "c++"],
            matched_programs=["TCS CodeVita"],
            eligibility_status=EligibilityStatus.ELIGIBLE,
            eligibility_reason="Eligible: Matches undergraduate requirements",
            priority="critical",
        )
        self.assertTrue(any("TCS CodeVita" in r for r in reasons))
        self.assertTrue(any("Competitive Programming" in r for r in reasons))
        self.assertTrue(any("Python" in r for r in reasons))
        self.assertTrue(any("CRITICAL" in r for r in reasons))


if __name__ == "__main__":
    unittest.main()
