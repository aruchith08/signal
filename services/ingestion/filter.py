"""
Fast Ingestion Filtering — Rule, regex, and keyword-based pre-filter
"""
import re
from typing import List, Optional, Sequence, Tuple

# Positive signals indicating potential student/developer opportunity
DEFAULT_POSITIVE_KEYWORDS = [
    # Core opportunity types
    r"\bregistr(?:ation|ations|er|ering)\b",
    r"\bregistrations? (?:are )?(?:now )?live\b",
    r"\bcontest(?:s)?\b",
    r"\bhackathon(?:s)?\b",
    r"\bcompet(?:ition|itions|e)\b",
    r"\bchallenge(?:s)?\b",
    r"\bstudent challenge\b",
    r"\bhiring challenge\b",
    r"\binnovation challenge\b",
    r"\bintern(?:ship|ships|s)?\b",
    r"\bfellowship(?:s)?\b",
    r"\bscholarship(?:s)?\b",
    r"\bcod(?:ing|e|er|ers)\b",
    r"\bbootcamp(?:s)?\b",
    r"\bgrant(?:s)?\b",
    r"\bsummer program(?:s)?\b",
    # Announcement phrasing
    r"\bapplications? (?:are )?(?:now )?open\b",
    r"\bcall for (?:applications|nominations|proposals|papers|entries)\b",
    r"\bentries invited\b",
    r"\bnominations (?:are )?open\b",
    r"\bdeadline extended\b",
    r"\bdeadlin(?:e|es)\b",
    r"\beligib(?:ility|le)\b",
    r"\bprize(?:s)?\b",
    r"\breward(?:s)?\b",
    r"\bhiring\b",
    r"\bproblem statement(?:s)?\b",
    r"\bsubmission(?:s)?\b",
    r"\bround(?:s)?\b",
]

# Negative patterns for disqualifying noise (sports scores, unrelated consumer news, etc.)
DEFAULT_NEGATIVE_PATTERNS = [
    r"\bcricket score\b",
    r"\bfootball score\b",
    r"\bbox office\b",
    r"\bmovie review\b",
    r"\bhoroscope\b",
    r"\bcelebrity gossip\b",
    r"\brecipe\b",
    r"\breal estate prices\b",
    r"\bhoroscope prediction\b",
]


class FastFilter:
    """
    High-speed deterministic filter guarding against unnecessary AI invocations.
    Configurable with custom positive and negative patterns to avoid false negatives.
    """

    def __init__(
        self,
        min_match_count: int = 1,
        extra_positive_patterns: Optional[Sequence[str]] = None,
        extra_negative_patterns: Optional[Sequence[str]] = None,
    ):
        self.min_match_count = min_match_count
        self._positive_patterns = list(DEFAULT_POSITIVE_KEYWORDS)
        if extra_positive_patterns:
            self._positive_patterns.extend(extra_positive_patterns)

        self._negative_patterns = list(DEFAULT_NEGATIVE_PATTERNS)
        if extra_negative_patterns:
            self._negative_patterns.extend(extra_negative_patterns)

        self._compile_patterns()

    def _compile_patterns(self) -> None:
        self._pos_regex = [re.compile(p, re.IGNORECASE) for p in self._positive_patterns]
        self._neg_regex = [re.compile(p, re.IGNORECASE) for p in self._negative_patterns]

    def add_positive_pattern(self, pattern: str) -> None:
        """Add a custom positive regex pattern and recompile."""
        self._positive_patterns.append(pattern)
        self._pos_regex.append(re.compile(pattern, re.IGNORECASE))

    def add_negative_pattern(self, pattern: str) -> None:
        """Add a custom negative regex pattern and recompile."""
        self._negative_patterns.append(pattern)
        self._neg_regex.append(re.compile(pattern, re.IGNORECASE))

    def evaluate(self, title: str, content: str) -> Tuple[bool, List[str], float]:
        """
        Evaluate candidate text.
        Returns:
            - is_candidate (bool): True if passes fast filter
            - matched_keywords (List[str]): List of pattern matches
            - score (float): Normalized candidate strength (0.0 - 1.0)
        """
        combined_text = f"{title or ''}\n{content or ''}"

        # Disqualify if negative pattern matched
        for neg in self._neg_regex:
            if neg.search(combined_text):
                return False, ["disqualified_by_negative_pattern"], 0.0

        matches: List[str] = []
        for pos in self._pos_regex:
            m = pos.search(combined_text)
            if m:
                matches.append(m.group(0).lower())

        is_candidate = len(matches) >= self.min_match_count
        score = min(1.0, len(matches) / 4.0)

        return is_candidate, matches, round(score, 2)


# Default pre-filter instance
fast_filter = FastFilter()
