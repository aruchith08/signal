"""
Domain Content Understanding & Classifier
Provides conservative deterministic classification of incoming discoveries into:
- OPPORTUNITY (new opportunity announcement)
- EVENT_UPDATE (registration open, round started, etc.)
- DEADLINE_UPDATE (deadline extended, date change)
- RESULT (results announced, shortlist released)
- INFORMATIONAL (tech articles, availability reports, status updates)
- IRRELEVANT (noise, spam)
"""
from datetime import datetime
import logging
import re
from typing import Any, Dict, Optional, Tuple
from pydantic import BaseModel, ConfigDict, Field

from shared.constants import (
    ContentClassification,
    EventType,
    OpportunityCategory,
)
from shared.utils import parse_iso_datetime


logger = logging.getLogger("signal.classifier")

# Common informational signals that should NOT be opportunities
INFORMATIONAL_PATTERNS = [
    r"\bavailability report\b",
    r"\bincident report\b",
    r"\bpostmortem\b",
    r"\bstatus report\b",
    r"\bsystem status\b",
    r"\boutage\b",
    r"\bdowntime\b",
    r"\bmaintenance\b",
    r"\bchangelog\b",
    r"\brelease notes\b",
    r"\bdecoding the\b",
    r"\bexploring\b",
    r"\bhow to\b",
    r"\btutorial\b",
    r"\barchitecture deep dive\b",
]

# Deadline change signals
DEADLINE_PATTERNS = [
    r"\bdeadline extended\b",
    r"\blast date extended\b",
    r"\bregistration extended\b",
    r"\bdate extension\b",
    r"\bextension of (?:the )?last date\b",
    r"\bdeadline postponed\b",
]

# Registration / Application opening signals
REGISTRATION_OPEN_PATTERNS = [
    r"\bregistrations? (?:are )?(?:now )?open\b",
    r"\bapplications? (?:are )?(?:now )?open\b",
    r"\bregistration is live\b",
    r"\bapply now\b",
    r"\bregistration portal active\b",
]

# Registration closing signals
REGISTRATION_CLOSED_PATTERNS = [
    r"\bregistrations? closed\b",
    r"\bapplications? closed\b",
    r"\bregistration ended\b",
    r"\bportal closed\b",
]

# Result / Shortlist signals
RESULT_PATTERNS = [
    r"\bresults? (?:are )?(?:announced|declared|out)\b",
    r"\bwinners? (?:are )?(?:announced|declared)\b",
    r"\bshortlist (?:is )?(?:released|published|out)\b",
    r"\bfinalists? announced\b",
    r"\bmerit list\b",
]

# Problem statement signals
PROBLEM_STATEMENT_PATTERNS = [
    r"\bproblem statements? released\b",
    r"\bproblem statement details\b",
    r"\bchallenges? announced\b",
]


class ContentUnderstanding(BaseModel):
    """Structured understanding of raw discovery content."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    classification: ContentClassification
    opportunity_name: Optional[str] = None
    canonical_name: Optional[str] = None
    organization_name: Optional[str] = None
    category: Optional[OpportunityCategory] = None
    lifecycle_event_type: Optional[EventType] = None
    event_title: Optional[str] = None
    event_date: Optional[datetime] = None
    deadline_date: Optional[datetime] = None
    season: Optional[str] = None
    year: Optional[int] = None
    target_audience: Optional[str] = None
    confidence: float = 0.85
    reasoning: str = ""
    is_actionable_opportunity: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)


class DomainClassifier:
    """Deterministic domain classifier and entity extraction helper."""

    @staticmethod
    def extract_season_and_year(title: str, content: str) -> Tuple[Optional[str], Optional[int]]:
        """Extract season/edition and year if mentioned in title or content."""
        season = None
        year = None

        combined = f"{title} {content}"

        # Season patterns e.g. "Season 13", "Season XIII", "Round 1009", "13th Edition"
        season_match = re.search(r"\b(?:season|edition|round)\s*([0-9]+|[ivxlcdm]+)\b", title, re.IGNORECASE)
        if season_match:
            season = season_match.group(1).upper()

        # Year pattern (2024 to 2035)
        year_match = re.search(r"\b(202[4-9]|203[0-5])\b", combined)
        if year_match:
            year = int(year_match.group(1))

        return season, year

    @staticmethod
    def extract_canonical_base_name(title: str) -> str:
        """Strip seasonal, round, or status suffixes to get clean base canonical name."""
        base = title
        # Remove prefixes like "SIH: ", "Codeforces: ", "Unstop: ", etc.
        base = re.sub(r"^(?:sih|codeforces|github|unstop):\s*", "", base, flags=re.IGNORECASE)
        # Remove announcement verbs
        base = re.sub(r"\b(?:announces?|announced)\b", "", base, flags=re.IGNORECASE)
        # Remove status phrases (with or without colon/dash delimiter)
        base = re.sub(
            r"(?:[:\-–]\s*)?\b(?:registrations? (?:are )?(?:now )?(?:open|closed)|registration deadline extended|deadline extended|results (?:are )?(?:announced|declared)|winners (?:are )?(?:announced|declared)|availability report)\b.*$",
            "",
            base,
            flags=re.IGNORECASE,
        )
        # Remove trailing season/round words
        base = re.sub(r"\b(?:season|round)\s*[0-9ivxlcdm]+\b", "", base, flags=re.IGNORECASE)
        base = re.sub(r"\b202[4-9]\b", "", base)
        # Clean whitespace
        base = re.sub(r"\s+", " ", base).strip(" -–:")
        return base or title

    @classmethod
    def infer_category(
        cls, text_lower: str, metadata_category: Optional[Any] = None
    ) -> Tuple[OpportunityCategory, float, str]:
        """Deterministic category classification mapping rules across all standard product domains."""
        if metadata_category:
            if isinstance(metadata_category, OpportunityCategory):
                return metadata_category, 0.95, "Metadata category"
            if isinstance(metadata_category, str):
                try:
                    return OpportunityCategory(metadata_category), 0.95, "Metadata category"
                except Exception:
                    pass

        # High-specificity keyword rules
        if any(k in text_lower for k in ["hackathon", "buildathon", "codeathon", "devpost", "sprint hackathon"]):
            return OpportunityCategory.HACKATHON, 0.95, "Hackathon pattern matched"
        if any(k in text_lower for k in ["kaggle", "hugging face", "machine learning competition", "deep learning challenge", "ai challenge", "model benchmark"]):
            return OpportunityCategory.AI_ML, 0.95, "AI/ML competition pattern matched"
        if any(k in text_lower for k in ["competitive programming", "codeforces", "codechef", "atcoder", "leetcode", "contest round", "cook-off", "starters", "codevita"]):
            return OpportunityCategory.COMPETITION, 0.95, "Competitive programming pattern matched"
        if any(k in text_lower for k in ["internship", "summer intern", "co-op", "apprentice", "trainee engineer"]):
            return OpportunityCategory.INTERNSHIP, 0.95, "Internship pattern matched"
        if any(k in text_lower for k in ["scholarship", "tuition grant", "merit scholarship", "financial aid scholarship"]):
            return OpportunityCategory.SCHOLARSHIP, 0.95, "Scholarship pattern matched"
        if any(k in text_lower for k in ["fellowship", "fellows program", "mentorship program", "lfx mentorship"]):
            return OpportunityCategory.FELLOWSHIP, 0.95, "Fellowship pattern matched"
        if any(k in text_lower for k in ["open source", "gsoc", "summer of code", "outreachy", "hacktoberfest", "github accelerator"]):
            return OpportunityCategory.OPEN_SOURCE, 0.95, "Open source pattern matched"
        if any(k in text_lower for k in ["job opening", "full-time role", "sde-1", "software engineer hiring"]):
            return OpportunityCategory.JOB, 0.90, "Job hiring pattern matched"
        if any(k in text_lower for k in ["certification", "certified professional", "credential exam", "official badge"]):
            return OpportunityCategory.CERTIFICATION, 0.90, "Certification pattern matched"
        if any(k in text_lower for k in ["conference", "symposium", "tech summit", "call for papers"]):
            return OpportunityCategory.CONFERENCE, 0.90, "Conference pattern matched"
        if any(k in text_lower for k in ["workshop", "bootcamp", "masterclass", "training session"]):
            return OpportunityCategory.WORKSHOP, 0.90, "Workshop pattern matched"
        if any(k in text_lower for k in ["entrance exam", "assessment test", "gate exam", "upsc examination"]):
            return OpportunityCategory.EXAM, 0.90, "Exam pattern matched"
        if any(k in text_lower for k in ["government initiative", "aicte scheme", "mygov challenge", "ministry initiative", "meity challenge", "national innovation"]):
            return OpportunityCategory.GOVERNMENT_PROGRAM, 0.95, "Government program pattern matched"
        if any(k in text_lower for k in ["student program", "campus ambassador", "student developer pack", "campus partner"]):
            return OpportunityCategory.STUDENT_PROGRAM, 0.90, "Student program pattern matched"

        return OpportunityCategory.OTHER, 0.50, "Default fallback category"

    @classmethod
    def classify(
        cls,
        raw_title: str,
        raw_content: str,
        connector_metadata: Optional[Dict[str, Any]] = None,
        source_category: Optional[str] = None,
        source_name: Optional[str] = None,
    ) -> ContentUnderstanding:
        """Classify discovery and determine actionable opportunity and lifecycle events."""
        metadata = connector_metadata or {}
        text = f"{raw_title}\n{raw_content}".strip()
        text_lower = text.lower()
        title_lower = raw_title.lower()

        season, year = cls.extract_season_and_year(raw_title, raw_content)
        canonical_base = cls.extract_canonical_base_name(raw_title)

        deadline_date: Optional[datetime] = None
        if metadata.get("deadline_date"):
            deadline_date = parse_iso_datetime(metadata["deadline_date"])

        if not deadline_date:
            try:
                from services.intelligence.date_extraction import DateExtractor
                dl_match = DateExtractor.extract_deadline(raw_content)
                if dl_match:
                    deadline_date = dl_match.parsed_date
            except Exception:
                pass

        meta_cat = metadata.get("category") or source_category
        parsed_category, cat_conf, cat_reason = cls.infer_category(text_lower, meta_cat)

        # 1. Informational / Non-opportunity check
        # If GitHub availability report or pure engineering writeup without competition/internship
        for pat in INFORMATIONAL_PATTERNS:
            if re.search(pat, title_lower):
                return ContentUnderstanding(
                    classification=ContentClassification.INFORMATIONAL,
                    opportunity_name=raw_title,
                    canonical_name=canonical_base,
                    organization_name=metadata.get("organization") or source_name,
                    confidence=0.95,
                    reasoning=f"Matched informational pattern: '{pat}'",
                    is_actionable_opportunity=False,
                )

        # 2. Results Announced
        for pat in RESULT_PATTERNS:
            if re.search(pat, text_lower):
                return ContentUnderstanding(
                    classification=ContentClassification.RESULT,
                    opportunity_name=raw_title,
                    canonical_name=canonical_base,
                    organization_name=metadata.get("organization") or source_name,
                    category=parsed_category,
                    lifecycle_event_type=EventType.RESULTS_ANNOUNCED,
                    event_title=f"Results Announced: {raw_title}",
                    season=season,
                    year=year,
                    deadline_date=deadline_date,
                    target_audience=metadata.get("eligibility"),
                    confidence=0.90,
                    reasoning=f"Matched result announcement pattern: '{pat}'",
                    is_actionable_opportunity=True,
                    metadata=metadata,
                )

        # 3. Deadline Update / Extension
        for pat in DEADLINE_PATTERNS:
            if re.search(pat, text_lower):
                return ContentUnderstanding(
                    classification=ContentClassification.DEADLINE_UPDATE,
                    opportunity_name=raw_title,
                    canonical_name=canonical_base,
                    organization_name=metadata.get("organization") or source_name,
                    category=parsed_category,
                    lifecycle_event_type=EventType.DEADLINE_EXTENDED,
                    event_title=f"Deadline Extended: {raw_title}",
                    season=season,
                    year=year,
                    deadline_date=deadline_date,
                    target_audience=metadata.get("eligibility"),
                    confidence=0.92,
                    reasoning=f"Matched deadline extension pattern: '{pat}'",
                    is_actionable_opportunity=True,
                    metadata=metadata,
                )

        # 4. Registration Open / Event Update
        for pat in REGISTRATION_OPEN_PATTERNS:
            if re.search(pat, text_lower):
                return ContentUnderstanding(
                    classification=ContentClassification.EVENT_UPDATE,
                    opportunity_name=raw_title,
                    canonical_name=canonical_base,
                    organization_name=metadata.get("organization") or source_name,
                    category=parsed_category,
                    lifecycle_event_type=EventType.REGISTRATION_OPEN,
                    event_title=f"Registrations Open: {raw_title}",
                    season=season,
                    year=year,
                    deadline_date=deadline_date,
                    target_audience=metadata.get("eligibility"),
                    confidence=0.90,
                    reasoning=f"Matched registration open pattern: '{pat}'",
                    is_actionable_opportunity=True,
                    metadata=metadata,
                )

        # 5. Registration Closed
        for pat in REGISTRATION_CLOSED_PATTERNS:
            if re.search(pat, text_lower):
                return ContentUnderstanding(
                    classification=ContentClassification.EVENT_UPDATE,
                    opportunity_name=raw_title,
                    canonical_name=canonical_base,
                    organization_name=metadata.get("organization") or source_name,
                    category=parsed_category,
                    lifecycle_event_type=EventType.REGISTRATION_CLOSED,
                    event_title=f"Registrations Closed: {raw_title}",
                    season=season,
                    year=year,
                    deadline_date=deadline_date,
                    target_audience=metadata.get("eligibility"),
                    confidence=0.90,
                    reasoning=f"Matched registration closed pattern: '{pat}'",
                    is_actionable_opportunity=True,
                    metadata=metadata,
                )

        # 6. Problem Statements Released
        for pat in PROBLEM_STATEMENT_PATTERNS:
            if re.search(pat, text_lower):
                return ContentUnderstanding(
                    classification=ContentClassification.EVENT_UPDATE,
                    opportunity_name=raw_title,
                    canonical_name=canonical_base,
                    organization_name=metadata.get("organization") or source_name,
                    category=parsed_category,
                    lifecycle_event_type=EventType.PROBLEM_STATEMENTS_RELEASED,
                    event_title=f"Problem Statements Released: {raw_title}",
                    season=season,
                    year=year,
                    deadline_date=deadline_date,
                    target_audience=metadata.get("eligibility"),
                    confidence=0.90,
                    reasoning=f"Matched problem statement release pattern: '{pat}'",
                    is_actionable_opportunity=True,
                    metadata=metadata,
                )

        # 7. Check for structured opportunity indicators (e.g. Codeforces contest phase, SIH problem statements)
        if metadata.get("contest_id") or "codeforces contest" in text_lower:
            phase = metadata.get("phase", "BEFORE")
            event_type = EventType.CONTEST_SCHEDULED if phase == "BEFORE" else EventType.EVENT_STARTED
            return ContentUnderstanding(
                classification=ContentClassification.OPPORTUNITY,
                opportunity_name=raw_title,
                canonical_name=canonical_base,
                organization_name="Codeforces",
                category=OpportunityCategory.COMPETITIVE_PROGRAMMING,
                lifecycle_event_type=event_type,
                event_title=f"Contest: {raw_title}",
                season=season,
                year=year,
                confidence=0.95,
                reasoning="Structured competitive programming contest",
                is_actionable_opportunity=True,
                metadata=metadata,
            )

        if metadata.get("ps_id") or "smart india hackathon problem statement" in text_lower:
            return ContentUnderstanding(
                classification=ContentClassification.OPPORTUNITY,
                opportunity_name=raw_title,
                canonical_name=canonical_base,
                organization_name=metadata.get("organization") or "Ministry / AICTE",
                category=OpportunityCategory.HACKATHON,
                lifecycle_event_type=EventType.PROBLEM_STATEMENTS_RELEASED,
                event_title=f"Challenge Released: {raw_title}",
                season=season,
                year=year,
                confidence=0.95,
                reasoning="Official Smart India Hackathon problem statement",
                is_actionable_opportunity=True,
                metadata=metadata,
            )

        # 8. General Opportunity Signal Detection
        opportunity_keywords = [
            "hackathon", "contest", "competition", "internship", "fellowship",
            "scholarship", "challenge", "student program", "fellows program",
            "codevita", "imagine cup", "grant", "bounty",
        ]
        has_opp_signal = any(k in text_lower for k in opportunity_keywords)

        if has_opp_signal:
            return ContentUnderstanding(
                classification=ContentClassification.OPPORTUNITY,
                opportunity_name=raw_title,
                canonical_name=canonical_base,
                organization_name=metadata.get("organization") or source_name,
                category=parsed_category,
                lifecycle_event_type=EventType.ANNOUNCED,
                event_title=f"Announced: {raw_title}",
                season=season,
                year=year,
                deadline_date=deadline_date,
                target_audience=metadata.get("eligibility"),
                confidence=0.85,
                reasoning="Opportunity keywords identified in content",
                is_actionable_opportunity=True,
                metadata=metadata,
            )

        # 9. Fallback: Check if pure informational article
        return ContentUnderstanding(
            classification=ContentClassification.INFORMATIONAL,
            opportunity_name=raw_title,
            canonical_name=canonical_base,
            organization_name=source_name,
            confidence=0.75,
            reasoning="No definitive opportunity or lifecycle signals detected",
            is_actionable_opportunity=False,
        )

    @classmethod
    async def classify_with_fallback(
        cls,
        raw_title: str,
        raw_content: str,
        connector_metadata: Optional[Dict[str, Any]] = None,
        source_category: Optional[str] = None,
        source_name: Optional[str] = None,
    ) -> ContentUnderstanding:
        """
        Deterministic-first classification with AI Gateway fallback when confidence is uncertain.
        Guarantees that deterministic rules are always evaluated first without latency or cost.
        """
        deterministic = cls.classify(
            raw_title=raw_title,
            raw_content=raw_content,
            connector_metadata=connector_metadata,
            source_category=source_category,
            source_name=source_name,
        )
        # If deterministic classification is confident and actionable, return immediately
        if deterministic.confidence >= 0.80 and deterministic.category not in (None, OpportunityCategory.OTHER):
            return deterministic

        # AI Gateway fallback only for low confidence or ambiguous categories
        try:
            from services.intelligence.router import ai_router
            text_snippet = f"{raw_title}\n{raw_content[:400]}"
            ai_res = await ai_router.classify(text_snippet)
            if ai_res and getattr(ai_res, "category", None):
                category_str = str(ai_res.category).lower()
                for cat in OpportunityCategory:
                    if cat.value in category_str or category_str in cat.value:
                        deterministic.category = cat
                        deterministic.confidence = max(deterministic.confidence, getattr(ai_res, "confidence", 0.85))
                        deterministic.reasoning += f" | AI Gateway refinement: {cat.value}"
                        break
        except Exception as ai_err:
            logger.debug(f"[Classifier] AI Gateway fallback skipped or failed: {ai_err}")

        return deterministic


# Compatibility alias
Classifier = DomainClassifier
