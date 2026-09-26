"""
Unit Tests for ConflictDetector
"""
import unittest
from services.verification.conflict_detector import ConflictDetector


class TestConflictDetector(unittest.TestCase):
    def test_detect_deadline_conflict(self):
        canonical = {"deadline_date": "2026-09-20T23:59:59Z", "year": 2026}
        incoming = {"deadline_date": "2026-09-25T23:59:59Z", "year": 2026}
        source_info = {"source_name": "unstop", "trust_score": 0.80}

        conflicts = ConflictDetector.detect_conflicts(canonical, incoming, source_info)
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0].field_name, "deadline")
        self.assertEqual(conflicts[0].conflicting_values, ["2026-09-20", "2026-09-25"])
        self.assertTrue(conflicts[0].is_critical)

    def test_detect_year_and_season_conflict(self):
        canonical = {"year": 2026, "season": "Season 12"}
        incoming = {"year": 2025, "season": "Season 13"}
        source_info = {"source_name": "news"}

        conflicts = ConflictDetector.detect_conflicts(canonical, incoming, source_info)
        field_names = [c.field_name for c in conflicts]
        self.assertIn("year", field_names)
        self.assertIn("season", field_names)

    def test_no_conflict_when_matching(self):
        canonical = {"deadline_date": "2026-09-20", "year": 2026}
        incoming = {"deadline_date": "2026-09-20", "year": 2026}
        conflicts = ConflictDetector.detect_conflicts(canonical, incoming, {})
        self.assertEqual(len(conflicts), 0)


if __name__ == "__main__":
    unittest.main()
