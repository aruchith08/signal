"""
Date Extraction & Deadline Intelligence Service
Detects, normalizes, and compares deadline and event dates from raw unstructured text.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
import re
from typing import List, Optional, Tuple
from shared.constants import EventType

# Month name mapping
MONTH_MAP = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}


@dataclass
class ExtractedDate:
    """Represents a date found in text with provenance."""
    label: str
    raw_text: str
    parsed_date: datetime
    is_deadline: bool = False


class DateExtractor:
    """Extracts and normalizes dates from unstructured text."""

    @classmethod
    def extract_dates(cls, text: str) -> List[ExtractedDate]:
        """Extract all identifiable dates from text."""
        if not text:
            return []

        results: List[ExtractedDate] = []

        # 1. Pattern: "10 September 2026" or "10th Sep 2026" or "10-Sep-2026"
        p1 = re.compile(
            r"\b(\d{1,2})(?:st|nd|rd|th)?[\s\-_]+([a-zA-Z]{3,9})[\s\-_]+(\d{4})\b",
            re.IGNORECASE,
        )
        for match in p1.finditer(text):
            day_str, month_str, year_str = match.groups()
            month_num = MONTH_MAP.get(month_str.lower())
            if month_num:
                try:
                    dt = datetime(int(year_str), month_num, int(day_str), tzinfo=timezone.utc)
                    raw = match.group(0)
                    is_dl = cls._is_deadline_context(text, match.start())
                    results.append(ExtractedDate(label="date", raw_text=raw, parsed_date=dt, is_deadline=is_dl))
                except ValueError:
                    pass

        # 2. Pattern: "September 10, 2026" or "Sep 10 2026"
        p2 = re.compile(
            r"\b([a-zA-Z]{3,9})[\s\-_]+(\d{1,2})(?:st|nd|rd|th)?(?:,)?[\s\-_]+(\d{4})\b",
            re.IGNORECASE,
        )
        for match in p2.finditer(text):
            month_str, day_str, year_str = match.groups()
            month_num = MONTH_MAP.get(month_str.lower())
            if month_num:
                try:
                    dt = datetime(int(year_str), month_num, int(day_str), tzinfo=timezone.utc)
                    raw = match.group(0)
                    is_dl = cls._is_deadline_context(text, match.start())
                    results.append(ExtractedDate(label="date", raw_text=raw, parsed_date=dt, is_deadline=is_dl))
                except ValueError:
                    pass

        # 3. Pattern: ISO Date "2026-09-10"
        p3 = re.compile(r"\b(\d{4})[/-](\d{1,2})[/-](\d{1,2})\b")
        for match in p3.finditer(text):
            year_str, month_str, day_str = match.groups()
            try:
                dt = datetime(int(year_str), int(month_str), int(day_str), tzinfo=timezone.utc)
                raw = match.group(0)
                is_dl = cls._is_deadline_context(text, match.start())
                results.append(ExtractedDate(label="date", raw_text=raw, parsed_date=dt, is_deadline=is_dl))
            except ValueError:
                pass

        # 4. Pattern: DD/MM/YYYY "10/09/2026"
        p4 = re.compile(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b")
        for match in p4.finditer(text):
            d_str, m_str, y_str = match.groups()
            try:
                dt = datetime(int(y_str), int(m_str), int(d_str), tzinfo=timezone.utc)
                raw = match.group(0)
                is_dl = cls._is_deadline_context(text, match.start())
                results.append(ExtractedDate(label="date", raw_text=raw, parsed_date=dt, is_deadline=is_dl))
            except ValueError:
                pass

        return results

    @classmethod
    def extract_deadline(cls, text: str) -> Optional[ExtractedDate]:
        """Extract the most probable deadline date from text."""
        dates = cls.extract_dates(text)
        # Prioritize explicit deadline context
        deadline_dates = [d for d in dates if d.is_deadline]
        if deadline_dates:
            return deadline_dates[0]
        # Fallback to the latest date found if any
        return max(dates, key=lambda d: d.parsed_date) if dates else None

    @staticmethod
    def _is_deadline_context(text: str, pos: int) -> bool:
        """Check if nearby text contains deadline keywords."""
        start = max(0, pos - 60)
        end = min(len(text), pos + 60)
        snippet = text[start:end].lower()
        keywords = ["deadline", "close", "closing", "last date", "end date", "due date", "until", "ends on"]
        return any(k in snippet for k in keywords)


class DeadlineEvaluator:
    """Evaluates whether a new deadline extends, shortens, or announces a deadline."""

    @staticmethod
    def evaluate(
        old_deadline: Optional[datetime],
        new_deadline: Optional[datetime],
    ) -> Tuple[Optional[EventType], str]:
        """Compare old deadline vs new deadline and determine lifecycle impact."""
        if not new_deadline:
            return None, "No new deadline specified"

        # Make sure both are timezone-aware UTC
        if old_deadline and old_deadline.tzinfo is None:
            old_deadline = old_deadline.replace(tzinfo=timezone.utc)
        if new_deadline.tzinfo is None:
            new_deadline = new_deadline.replace(tzinfo=timezone.utc)

        if old_deadline is None:
            formatted = new_deadline.strftime("%d %B %Y")
            return EventType.DEADLINE_ANNOUNCED, f"Registration deadline announced for {formatted}"

        if new_deadline > old_deadline:
            old_str = old_deadline.strftime("%d %B %Y")
            new_str = new_deadline.strftime("%d %B %Y")
            return EventType.DEADLINE_EXTENDED, f"Registration deadline extended from {old_str} to {new_str}"

        if new_deadline < old_deadline:
            old_str = old_deadline.strftime("%d %B %Y")
            new_str = new_deadline.strftime("%d %B %Y")
            return EventType.DEADLINE_SHORTENED, f"Registration deadline shortened from {old_str} to {new_str}"

        return None, "Deadline unchanged"
