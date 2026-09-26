"""
Verification Engine & Consensus Subsystem
Orchestrates multi-source consensus, fact-level verification, conflict recording,
source trust integration, and composite verification scoring.
"""
from datetime import datetime, timezone
import json
import logging
from typing import Any, Dict, List, Optional
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from apps.api.models.opportunity import Opportunity
from apps.api.models.verification import (
    OpportunitySource,
    VerifiedField,
    VerificationConflict,
)
from services.verification.source_trust import SourceTrustService
from services.verification.conflict_detector import ConflictDetector, FieldConflict
from shared.constants import (
    ConflictStatus,
    FieldVerificationStatus,
    VerificationStatus,
)

logger = logging.getLogger("signal.verification_engine")


class VerificationResult(BaseModel):
    status: str
    confidence: float
    source_count: int
    official_source_present: bool
    consensus_score: float
    reasons: List[str] = []


class VerificationEngine:
    """Consensus engine for aggregating source evidence and verifying canonical opportunities."""

    def __init__(self, db: AsyncSession, trust_service: Optional[SourceTrustService] = None):
        self.db = db
        self.trust_service = trust_service or SourceTrustService()

    async def register_source_contribution(
        self,
        opportunity_id: str,
        source_url: str,
        canonical_url: str,
        source_id: Optional[str] = None,
        raw_discovery_id: Optional[str] = None,
        source_title: Optional[str] = None,
        contributed_fields: Optional[List[str]] = None,
    ) -> OpportunitySource:
        """Record or update a contributing source for an opportunity."""
        trust_score, is_official = self.trust_service.evaluate_url(canonical_url)

        # Check existing OpportunitySource
        stmt = select(OpportunitySource).where(
            OpportunitySource.opportunity_id == opportunity_id,
            OpportunitySource.canonical_url == canonical_url,
        )
        existing_src = (await self.db.execute(stmt)).scalars().first()

        fields_json = json.dumps(contributed_fields or [])
        if existing_src:
            existing_src.trust_score = trust_score
            existing_src.is_official_source = is_official
            existing_src.contributed_fields = fields_json
            if source_title:
                existing_src.source_title = source_title
            await self.db.flush()
            return existing_src

        # Determine if this is the first (primary) source
        count_stmt = select(OpportunitySource).where(OpportunitySource.opportunity_id == opportunity_id)
        existing_count = len((await self.db.execute(count_stmt)).scalars().all())

        new_source = OpportunitySource(
            opportunity_id=opportunity_id,
            source_id=source_id,
            raw_discovery_id=raw_discovery_id,
            source_url=source_url,
            canonical_url=canonical_url,
            source_title=source_title,
            trust_score=trust_score,
            is_primary_source=(existing_count == 0),
            is_official_source=is_official,
            contributed_fields=fields_json,
        )
        self.db.add(new_source)
        await self.db.flush()
        logger.info(
            f"[VerificationEngine] Registered contributing source for {opportunity_id}: "
            f"trust={trust_score:.2f} official={is_official}"
        )
        return new_source

    async def verify_field(
        self,
        opportunity_id: str,
        field_name: str,
        new_value: Optional[str],
        source_is_official: bool = False,
        source_trust: float = 0.50,
    ) -> VerifiedField:
        """
        Record or update a fact-level field with consensus voting.
        Official sources dominate existing values.
        """
        stmt = select(VerifiedField).where(
            VerifiedField.opportunity_id == opportunity_id,
            VerifiedField.field_name == field_name,
        )
        field_obj = (await self.db.execute(stmt)).scalars().first()

        if not field_obj:
            field_obj = VerifiedField(
                opportunity_id=opportunity_id,
                field_name=field_name,
                value=new_value,
                confidence=round(source_trust, 2),
                source_count=1,
                official_confirmation=source_is_official,
                verification_status=(
                    FieldVerificationStatus.VERIFIED.value
                    if source_is_official or source_trust >= 0.80
                    else FieldVerificationStatus.LIKELY.value
                ),
            )
            self.db.add(field_obj)
            await self.db.flush()
            return field_obj

        # Update existing field consensus
        field_obj.source_count += 1
        if source_is_official:
            # Official source overrides or confirms
            field_obj.official_confirmation = True
            field_obj.value = new_value
            field_obj.confidence = 0.95
            field_obj.verification_status = FieldVerificationStatus.VERIFIED.value
        elif field_obj.value == new_value:
            # Another source confirms identical value
            field_obj.confidence = min(0.98, round(field_obj.confidence + 0.10, 2))
            field_obj.verification_status = FieldVerificationStatus.VERIFIED.value
        else:
            # Disagreement without official dominance
            if not field_obj.official_confirmation:
                field_obj.verification_status = FieldVerificationStatus.CONFLICTING.value

        await self.db.flush()
        return field_obj

    async def evaluate_and_update_opportunity(
        self,
        opportunity_id: str,
        incoming_data: Optional[Dict[str, Any]] = None,
        incoming_source_info: Optional[Dict[str, Any]] = None,
    ) -> VerificationResult:
        """
        Compute overall verification consensus, detect conflicts, and update opportunity record.
        """
        opp_stmt = select(Opportunity).where(Opportunity.id == opportunity_id)
        opp = (await self.db.execute(opp_stmt)).scalars().first()
        if not opp:
            raise ValueError(f"Opportunity {opportunity_id} not found")

        # 1. Fetch contributing sources
        sources_stmt = select(OpportunitySource).where(OpportunitySource.opportunity_id == opportunity_id)
        sources = (await self.db.execute(sources_stmt)).scalars().all()

        source_count = len(sources)
        has_official = any(s.is_official_source for s in sources)
        avg_trust = (sum(s.trust_score for s in sources) / source_count) if source_count else 0.50

        # 2. Conflict Detection if incoming data provided
        if incoming_data and incoming_source_info:
            # Look up existing deadline from events or verified_fields
            canonical_deadline = opp.events[0].deadline_date if opp.events else None
            if not canonical_deadline:
                vf_stmt = select(VerifiedField).where(
                    VerifiedField.opportunity_id == opportunity_id,
                    VerifiedField.field_name == "deadline",
                )
                vf = (await self.db.execute(vf_stmt)).scalars().first()
                if vf:
                    canonical_deadline = vf.value

            canonical_data = {
                "deadline_date": canonical_deadline,
                "application_url": opp.application_url,
                "eligibility": opp.eligibility,
                "year": opp.year,
                "season": opp.season,
            }
            conflicts = ConflictDetector.detect_conflicts(canonical_data, incoming_data, incoming_source_info)
            for conf in conflicts:
                # Add conflict record
                conf_record = VerificationConflict(
                    opportunity_id=opportunity_id,
                    field_name=conf.field_name,
                    conflicting_values=json.dumps(conf.conflicting_values),
                    source_details=json.dumps(conf.source_details),
                    status=ConflictStatus.OPEN.value,
                    resolution_notes="Detected during cross-source ingestion",
                )
                self.db.add(conf_record)

        # Check existing open conflicts
        conflicts_stmt = select(VerificationConflict).where(
            VerificationConflict.opportunity_id == opportunity_id,
            VerificationConflict.status == ConflictStatus.OPEN.value,
        )
        open_conflicts = (await self.db.execute(conflicts_stmt)).scalars().all()

        # 3. Consensus Status Determination
        reasons = []
        if has_official and not open_conflicts:
            status = VerificationStatus.VERIFIED.value
            confidence = min(0.99, max(0.92, avg_trust))
            reasons.append("Official primary source confirmed")
        elif source_count >= 2 and not open_conflicts:
            status = VerificationStatus.VERIFIED.value
            confidence = min(0.95, round(avg_trust + 0.10, 2))
            reasons.append("Multi-source agreement confirmed")
        elif open_conflicts:
            status = VerificationStatus.CONFLICTING.value
            confidence = 0.60
            reasons.append(f"{len(open_conflicts)} unresolved field conflicts detected")
        elif avg_trust >= 0.75:
            status = VerificationStatus.LIKELY_VERIFIED.value
            confidence = round(avg_trust, 2)
            reasons.append("Reputable platform reporting")
        else:
            status = VerificationStatus.UNVERIFIED.value
            confidence = round(avg_trust, 2)
            reasons.append("Single unverified source reporting")

        # 4. Update Opportunity Record
        opp.verification_status = status
        opp.verification_confidence = confidence
        opp.source_count = source_count
        opp.official_source_present = has_official
        opp.last_verified_at = datetime.now(timezone.utc)
        opp.official = has_official

        await self.db.flush()

        return VerificationResult(
            status=status,
            confidence=confidence,
            source_count=source_count,
            official_source_present=has_official,
            consensus_score=round(avg_trust, 2),
            reasons=reasons,
        )
