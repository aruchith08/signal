"""
Watch Service Package — Monitored Program Matching, Scoring, and Lifecycle Tracking
"""
from services.watch.matcher import ProgramWatchMatcher, WatchMatchResult
from services.watch.scoring import WatchMatchScorer
from services.watch.engine import ProgramWatchEngine

__all__ = [
    "ProgramWatchMatcher",
    "WatchMatchResult",
    "WatchMatchScorer",
    "ProgramWatchEngine",
]
