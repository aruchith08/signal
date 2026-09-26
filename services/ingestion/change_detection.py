"""
Change Detection & Meaningful Change Filtering Service
Detects semantic deltas between source snapshots while filtering out noise (timestamps, formatting, banners).
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import logging
import re
from typing import List, Optional, Set, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from apps.api.models.snapshot import SourceSnapshot
from apps.api.models.source import Source
from services.intelligence.date_extraction import DateExtractor, DeadlineEvaluator
from shared.constants import ChangeType, EventType
from shared.utils import compute_content_hash

logger = logging.getLogger("signal.ingestion.change_detection")


@dataclass
class ChangeEvaluation:
    """Outcome of evaluating current content against historical snapshot."""
    change_type: ChangeType
    is_meaningful: bool
    reasons: List[str] = field(default_factory=list)
    previous_snapshot_id: Optional[str] = None
    extracted_deadline: Optional[datetime] = None
    deadline_event_type: Optional[EventType] = None


class MeaningfulChangeDetector:
    """Filters cosmetic, volatile noise and identifies impactful opportunity changes."""

    # Patterns to strip when determining if a change is meaningful
    VOLATILE_PATTERNS = [
        re.compile(r"last\s+updated\s*(?:at|on)?\s*[:\-]?\s*[\d:\sAPMapm/\-_]+", re.IGNORECASE),
        re.compile(r"current\s+time\s*[:\-]?\s*[\d:\sAPMapm/\-_]+", re.IGNORECASE),
        re.compile(r"fetched\s*(?:at|on)?\s*[:\-]?\s*[\d:\sAPMapm/\-_]+", re.IGNORECASE),
        re.compile(r"page\s+views?\s*[:\-]?\s*[\d,]+", re.IGNORECASE),
        re.compile(r"visitors?\s*[:\-]?\s*[\d,]+", re.IGNORECASE),
        re.compile(r"copyright\s*©?\s*\d{4}", re.IGNORECASE),
        re.compile(r"cookie\s+policy|accept\s+cookies|we\s+use\s+cookies", re.IGNORECASE),
        re.compile(r"privacy\s+policy|terms\s+of\s+service", re.IGNORECASE),
    ]

    SIGNIFICANT_KEYWORDS = [
        "registration open",
        "registrations open",
        "registration closed",
        "registrations closed",
        "deadline extended",
        "deadline changed",
        "last date to apply",
        "applications open",
        "applications closed",
        "results announced",
        "shortlist released",
        "problem statements released",
        "winners announced",
        "dates announced",
        "round started",
        "contest scheduled",
    ]

    @classmethod
    def normalize_for_comparison(cls, text: str) -> str:
        """Strip volatile noise, collapse whitespace, and lowercase for semantic comparison."""
        if not text:
            return ""

        clean = text
        for pat in cls.VOLATILE_PATTERNS:
            clean = pat.sub(" ", clean)

        # Collapse multiple whitespace and normalize case
        clean = re.sub(r"\s+", " ", clean).strip().lower()
        return clean

    @classmethod
    def evaluate_difference(
        cls,
        old_text: str,
        new_text: str,
        old_items_count: int = 0,
        new_items_count: int = 0,
    ) -> ChangeEvaluation:
        """Compare normalized text and item counts to detect meaningful changes."""
        norm_old = cls.normalize_for_comparison(old_text)
        norm_new = cls.normalize_for_comparison(new_text)

        # 1. Exact normalized match = No Change
        if norm_old == norm_new and old_items_count == new_items_count:
            return ChangeEvaluation(
                change_type=ChangeType.NO_CHANGE,
                is_meaningful=False,
                reasons=["Content matches previous snapshot after noise normalization"],
            )

        # 2. Count differences indicate added or removed items
        reasons: List[str] = []
        change_type = ChangeType.CONTENT_CHANGED
        is_meaningful = False

        if new_items_count > old_items_count:
            change_type = ChangeType.NEW_ITEM
            is_meaningful = True
            reasons.append(f"Discovered new items ({new_items_count} vs {old_items_count})")
        elif new_items_count < old_items_count and new_items_count > 0:
            change_type = ChangeType.ITEM_REMOVED
            is_meaningful = True
            reasons.append(f"Items removed or expired ({new_items_count} vs {old_items_count})")

        # 3. Check for status keywords shift
        old_keywords = {k for k in cls.SIGNIFICANT_KEYWORDS if k in norm_old}
        new_keywords = {k for k in cls.SIGNIFICANT_KEYWORDS if k in norm_new}
        added_keywords = new_keywords - old_keywords

        if added_keywords:
            change_type = ChangeType.STATUS_CHANGED
            is_meaningful = True
            reasons.append(f"Lifecycle status phrases appeared: {', '.join(added_keywords)}")

        # 4. Check for deadline changes
        old_dl = DateExtractor.extract_deadline(old_text)
        new_dl = DateExtractor.extract_deadline(new_text)

        dl_event_type = None
        extracted_dl_date = new_dl.parsed_date if new_dl else None

        if new_dl and (not old_dl or old_dl.parsed_date != new_dl.parsed_date):
            ev_type, reason_str = DeadlineEvaluator.evaluate(
                old_dl.parsed_date if old_dl else None,
                new_dl.parsed_date,
            )
            if ev_type:
                change_type = ChangeType.DEADLINE_CHANGED
                is_meaningful = True
                dl_event_type = ev_type
                reasons.append(reason_str)

        # 5. If text changed but no specific reason found, check length difference
        if not reasons:
            if abs(len(norm_new) - len(norm_old)) > 50:
                is_meaningful = True
                change_type = ChangeType.CONTENT_CHANGED
                reasons.append("Significant content text length modification")
            else:
                # Minor wording/cosmetic change
                is_meaningful = False
                change_type = ChangeType.NO_CHANGE
                reasons.append("Minor cosmetic or formatting change ignored")

        return ChangeEvaluation(
            change_type=change_type,
            is_meaningful=is_meaningful,
            reasons=reasons,
            extracted_deadline=extracted_dl_date,
            deadline_event_type=dl_event_type,
        )


class SnapshotManager:
    """Manages recording and comparing SourceSnapshot database records."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_latest_snapshot(self, source_id: str) -> Optional[SourceSnapshot]:
        """Fetch the most recent snapshot for a given source."""
        stmt = (
            select(SourceSnapshot)
            .where(SourceSnapshot.source_id == source_id)
            .order_by(desc(SourceSnapshot.fetched_at))
            .limit(1)
        )
        return (await self.session.execute(stmt)).scalars().first()

    async def record_snapshot(
        self,
        source_id: str,
        raw_content: str,
        items_count: int,
        metadata: Optional[dict] = None,
    ) -> Tuple[SourceSnapshot, ChangeEvaluation]:
        """Record snapshot, compare with previous, and determine change evaluation."""
        now = datetime.now(timezone.utc)
        normalized = MeaningfulChangeDetector.normalize_for_comparison(raw_content)
        content_hash = compute_content_hash(raw_content)
        snapshot_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()

        prev_snapshot = await self.get_latest_snapshot(source_id)

        if prev_snapshot:
            evaluation = MeaningfulChangeDetector.evaluate_difference(
                old_text=prev_snapshot.normalized_content or prev_snapshot.raw_content or "",
                new_text=normalized,
                old_items_count=prev_snapshot.items_count,
                new_items_count=items_count,
            )
            evaluation.previous_snapshot_id = prev_snapshot.id
        else:
            evaluation = ChangeEvaluation(
                change_type=ChangeType.NEW_ITEM,
                is_meaningful=True,
                reasons=["Initial baseline snapshot created"],
            )

        snapshot = SourceSnapshot(
            source_id=source_id,
            snapshot_hash=snapshot_hash,
            content_hash=content_hash,
            normalized_content=normalized[:50000] if normalized else None,
            raw_content=raw_content[:50000] if raw_content else None,
            items_count=items_count,
            fetched_at=now,
            status="changed" if evaluation.is_meaningful else "unchanged",
            change_type=evaluation.change_type.value,
            metadata_json=metadata or {},
        )
        self.session.add(snapshot)
        await self.session.flush()

        return snapshot, evaluation
