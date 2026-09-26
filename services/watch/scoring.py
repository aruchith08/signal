"""
Watch Match Scoring — Centralized thresholds and confidence classification for monitored program matches
"""
from shared.constants import WatchConfidence


class WatchMatchScorer:
    """Centralized score classification and threshold evaluations."""

    CONFIDENCE_HIGH_THRESHOLD: float = 0.90
    CONFIDENCE_MEDIUM_THRESHOLD: float = 0.60

    @classmethod
    def categorize(cls, score: float) -> WatchConfidence:
        """Categorize a numerical score (0.0 to 1.0) into High, Medium, or Low confidence."""
        if score >= cls.CONFIDENCE_HIGH_THRESHOLD:
            return WatchConfidence.HIGH
        elif score >= cls.CONFIDENCE_MEDIUM_THRESHOLD:
            return WatchConfidence.MEDIUM
        return WatchConfidence.LOW

    @classmethod
    def is_actionable(cls, score: float) -> bool:
        """Matches with medium or high confidence are considered actionable program watch hits."""
        return score >= cls.CONFIDENCE_MEDIUM_THRESHOLD

    @classmethod
    def is_high_confidence(cls, score: float) -> bool:
        """Checks if match score satisfies high-confidence alert threshold."""
        return score >= cls.CONFIDENCE_HIGH_THRESHOLD
