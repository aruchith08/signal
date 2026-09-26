"""
Phase 3 Verification and Multi-Source Intelligence Models
Tracks contributing sources, field-level verification, conflicts, semantic candidates, and human reviews.
"""
from typing import TYPE_CHECKING, List, Optional
from datetime import datetime
from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text, UniqueConstraint, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from apps.api.database import Base
from apps.api.models.base import TimestampMixin, UUIDPrimaryKeyMixin
from shared.constants import (
    CandidateStatus,
    ConflictStatus,
    FieldVerificationStatus,
    ReviewPriority,
    ReviewStatus,
)

if TYPE_CHECKING:
    from apps.api.models.opportunity import Opportunity
    from apps.api.models.source import Source
    from apps.api.models.discovery import RawDiscovery


class OpportunitySource(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Tracks every source that contributed information to a canonical opportunity."""
    __tablename__ = "opportunity_sources"

    opportunity_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("opportunities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("sources.id", ondelete="SET NULL"), nullable=True, index=True
    )
    raw_discovery_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("raw_discoveries.id", ondelete="SET NULL"), nullable=True, index=True
    )

    source_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    canonical_url: Mapped[str] = mapped_column(String(1024), nullable=False, index=True)
    source_title: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    trust_score: Mapped[float] = mapped_column(Float, default=0.50, nullable=False)
    is_primary_source: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_official_source: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    contributed_fields: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    opportunity: Mapped["Opportunity"] = relationship("Opportunity", back_populates="sources")
    source: Mapped[Optional["Source"]] = relationship("Source")
    raw_discovery: Mapped[Optional["RawDiscovery"]] = relationship("RawDiscovery")

    __table_args__ = (
        UniqueConstraint("opportunity_id", "canonical_url", name="uq_opportunity_source_canonical_url"),
    )


class VerifiedField(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Fact-level verification for specific attributes of an opportunity."""
    __tablename__ = "verified_fields"

    opportunity_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("opportunities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    field_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.50, nullable=False)
    source_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    official_confirmation: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    verification_status: Mapped[str] = mapped_column(
        String(50), default=FieldVerificationStatus.UNVERIFIED.value, nullable=False, index=True
    )

    # Relationships
    opportunity: Mapped["Opportunity"] = relationship("Opportunity", back_populates="verified_fields")

    __table_args__ = (
        UniqueConstraint("opportunity_id", "field_name", name="uq_verified_field_opp_name"),
    )


class VerificationConflict(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Records discrepancies between contributing sources for a specific field."""
    __tablename__ = "verification_conflicts"

    opportunity_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("opportunities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    field_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    conflicting_values: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(50), default=ConflictStatus.OPEN.value, nullable=False, index=True
    )
    resolution_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    opportunity: Mapped["Opportunity"] = relationship("Opportunity", back_populates="conflicts")


class SemanticMatchCandidate(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Candidate relationship between two opportunities identified via semantic similarity or heuristics."""
    __tablename__ = "semantic_match_candidates"

    opportunity_a_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("opportunities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    opportunity_b_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("opportunities.id", ondelete="CASCADE"), nullable=False, index=True
    )

    similarity_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    deterministic_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    ai_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    final_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    status: Mapped[str] = mapped_column(
        String(50), default=CandidateStatus.PENDING.value, nullable=False, index=True
    )
    decision_reason: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    opportunity_a: Mapped["Opportunity"] = relationship(
        "Opportunity", foreign_keys=[opportunity_a_id], back_populates="candidates_as_a"
    )
    opportunity_b: Mapped["Opportunity"] = relationship(
        "Opportunity", foreign_keys=[opportunity_b_id], back_populates="candidates_as_b"
    )

    __table_args__ = (
        UniqueConstraint("opportunity_a_id", "opportunity_b_id", name="uq_candidate_pair"),
    )


class VerificationReview(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Human review queue for ambiguous opportunity merges or unresolved critical conflicts."""
    __tablename__ = "verification_reviews"

    entity_type: Mapped[str] = mapped_column(String(50), default="opportunity", nullable=False, index=True)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    candidate_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("semantic_match_candidates.id", ondelete="SET NULL"), nullable=True
    )
    conflict_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("verification_conflicts.id", ondelete="SET NULL"), nullable=True
    )

    reason: Mapped[str] = mapped_column(String(512), nullable=False)
    priority: Mapped[str] = mapped_column(
        String(20), default=ReviewPriority.MEDIUM.value, nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String(50), default=ReviewStatus.OPEN.value, nullable=False, index=True
    )
    review_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resolution_action: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    candidate: Mapped[Optional["SemanticMatchCandidate"]] = relationship("SemanticMatchCandidate")
    conflict: Mapped[Optional["VerificationConflict"]] = relationship("VerificationConflict")
