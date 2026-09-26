"""
Mock AI Provider — Deterministic responses for testing, development, and offline mode.
"""
import re
from datetime import datetime, timezone, timedelta
from typing import Optional
from services.intelligence.base_provider import BaseAIProvider
from services.intelligence.models import (
    ClassificationResult,
    ExtractionResult,
    SummarizationResult,
)
from shared.constants import OpportunityCategory, OpportunityStatus, EventType


class MockAIProvider(BaseAIProvider):
    """Deterministic Mock AI Provider that parses text patterns or provides sensible defaults."""

    def __init__(self, name: str = "mock"):
        super().__init__(name=name)

    async def is_available(self) -> bool:
        return True

    def _infer_category(self, content_lower: str) -> OpportunityCategory:
        if any(k in content_lower for k in ["codevita", "contest", "leetcode", "codeforces", "codechef", "atcoder"]):
            return OpportunityCategory.COMPETITIVE_PROGRAMMING
        if any(k in content_lower for k in ["hackathon", "devfolio", "unstop", "sih", "smart india hackathon"]):
            return OpportunityCategory.HACKATHON
        if any(k in content_lower for k in ["kaggle", "machine learning", "deep learning", "nlp", "computer vision", "hugging face"]):
            return OpportunityCategory.AI_ML
        if any(k in content_lower for k in ["meity", "aicte", "indiaai", "isro", "drdo", "mygov", "government"]):
            return OpportunityCategory.GOVERNMENT
        if any(k in content_lower for k in ["internship", "summer intern", "sde intern", "student intern"]):
            return OpportunityCategory.INTERNSHIP
        if any(k in content_lower for k in ["fellowship", "scholarship", "grant"]):
            return OpportunityCategory.SCHOLARSHIP_FELLOWSHIP
        if any(k in content_lower for k in ["tcs", "infosys", "microsoft", "google", "flipkart", "amazon"]):
            return OpportunityCategory.MAJOR_COMPANY_PROGRAM
        return OpportunityCategory.EDUCATION_RESEARCH

    def _infer_organization(self, content: str) -> Optional[str]:
        org_patterns = [
            (r"\bTCS\b|\bTata Consultancy Services\b", "TCS"),
            (r"\bInfosys\b", "Infosys"),
            (r"\bGoogle\b", "Google"),
            (r"\bMicrosoft\b", "Microsoft"),
            (r"\bFlipkart\b", "Flipkart"),
            (r"\bSmart India Hackathon\b|\bAICTE\b", "AICTE / MoE"),
            (r"\bMeitY\b", "MeitY"),
            (r"\bCodeChef\b", "CodeChef"),
            (r"\bCodeforces\b", "Codeforces"),
            (r"\bKaggle\b", "Kaggle"),
        ]
        for pattern, org in org_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                return org
        return "National Tech Initiative"

    async def classify(self, content: str) -> ClassificationResult:
        content_lower = content.lower()
        opportunity_signals = [
            "registration", "contest", "hackathon", "challenge", "competition",
            "deadline", "apply", "internship", "fellowship", "scholarship", "prize",
            "eligibility", "round"
        ]
        matches = [sig for sig in opportunity_signals if sig in content_lower]
        is_opp = len(matches) >= 1

        category = self._infer_category(content_lower) if is_opp else None
        confidence = min(0.95, 0.50 + len(matches) * 0.1) if is_opp else 0.20

        return ClassificationResult(
            is_opportunity=is_opp,
            category=category,
            confidence=round(confidence, 2),
            reasoning=f"Detected opportunity signals: {', '.join(matches[:4])}" if is_opp else "No opportunity keywords matched",
            provider=self.name,
        )

    async def extract(self, content: str) -> ExtractionResult:
        content_lower = content.lower()
        category = self._infer_category(content_lower)
        org = self._infer_organization(content)

        # Extract or generate title
        lines = [line.strip() for line in content.split("\n") if line.strip()]
        title = lines[0] if lines else "Extracted Tech Opportunity"
        if len(title) > 80:
            title = title[:77] + "..."

        now = datetime.now(timezone.utc)
        deadline = now + timedelta(days=14)

        events = [
            {
                "event_type": EventType.REGISTRATION_OPEN.value,
                "title": f"Registrations Open for {title}",
                "event_date": now.isoformat(),
                "deadline_date": None,
                "is_critical": False,
            },
            {
                "event_type": EventType.REGISTRATION_CLOSING.value,
                "title": f"Registration Deadline for {title}",
                "event_date": None,
                "deadline_date": deadline.isoformat(),
                "is_critical": True,
            }
        ]

        return ExtractionResult(
            title=title,
            organization=org,
            category=category,
            event_type="competition" if "contest" in content_lower or "hackathon" in content_lower else "program",
            status=OpportunityStatus.REGISTRATION_OPEN,
            eligibility="Undergraduate students (B.Tech / B.E / Dual Degree / BCA / MCA)",
            target_audience="Engineering students, competitive programmers, and developers",
            application_url="https://signal.internal/apply",
            events=events,
            summary=f"{title} organized by {org or 'organizers'}. Open for registrations with upcoming deadlines.",
            confidence=0.92,
            provider=self.name,
        )

    async def summarize(self, content: str) -> SummarizationResult:
        lines = [l.strip() for l in content.split("\n") if l.strip()]
        topic = lines[0] if lines else "Opportunity"
        return SummarizationResult(
            summary=f"Key details and guidelines for {topic}.",
            key_highlights=[
                "Official student challenge with national industry visibility",
                "Certificates, hiring interviews, and cash rewards for top performers",
                "Structured multi-round evaluation format",
            ],
            action_items=[
                "Verify eligibility requirements",
                "Register on the official portal before the closing deadline",
                "Form team / prepare programming environment",
            ],
            provider=self.name,
        )
