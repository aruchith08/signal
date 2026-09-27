"""
Opportunity ORM Model — The core domain entity of SIGNAL
"""
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from apps.api.database import Base
from apps.api.models.base import TimestampMixin, UUIDPrimaryKeyMixin
from shared.constants import OpportunityCategory, OpportunityStatus, VerificationStatus

if TYPE_CHECKING:
    from apps.api.models.organization import Organization
    from apps.api.models.source import Source
    from apps.api.models.event import OpportunityEvent
    from apps.api.models.notification import Notification
    from apps.api.models.alias import OpportunityAlias
    from apps.api.models.verification import (
        OpportunitySource,
        VerifiedField,
        VerificationConflict,
        SemanticMatchCandidate,
    )
    from apps.api.models.interaction import UserOpportunityInteraction


class Opportunity(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "opportunities"

    title: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    canonical_name: Mapped[Optional[str]] = mapped_column(String(512), nullable=True, index=True)
    slug: Mapped[str] = mapped_column(String(512), unique=True, nullable=False, index=True)
    season: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    current_state: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    organization_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    source_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("sources.id", ondelete="SET NULL"), nullable=True, index=True
    )
    category: Mapped[str] = mapped_column(
        String(50), default=OpportunityCategory.COMPETITIVE_PROGRAMMING.value, nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(String(50), default="competition", nullable=False)
    status: Mapped[str] = mapped_column(
        String(50), default=OpportunityStatus.ACTIVE.value, nullable=False, index=True
    )
    verification_status: Mapped[str] = mapped_column(
        String(50), default=VerificationStatus.DISCOVERED.value, nullable=False, index=True
    )
    confidence_score: Mapped[int] = mapped_column(Integer, default=50, nullable=False)
    official: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    priority: Mapped[str] = mapped_column(String(50), default="medium", nullable=False, index=True)
    country: Mapped[Optional[str]] = mapped_column(String(100), default="India", nullable=True)
    eligibility: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    target_audience: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    required_skills: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tags: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    application_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    raw_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    content_hash: Mapped[Optional[str]] = mapped_column(String(64), unique=True, index=True, nullable=True)

    # Phase 3 Verification Extensions
    verification_confidence: Mapped[float] = mapped_column(Float, default=0.50, nullable=False)
    source_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    official_source_present: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    organization: Mapped[Optional["Organization"]] = relationship(
        "Organization", back_populates="opportunities"
    )
    source: Mapped[Optional["Source"]] = relationship(
        "Source", back_populates="opportunities"
    )
    events: Mapped[List["OpportunityEvent"]] = relationship(
        "OpportunityEvent", back_populates="opportunity", cascade="all, delete-orphan", lazy="selectin"
    )
    aliases: Mapped[List["OpportunityAlias"]] = relationship(
        "OpportunityAlias", back_populates="opportunity", cascade="all, delete-orphan", lazy="selectin"
    )
    notifications: Mapped[List["Notification"]] = relationship(
        "Notification", back_populates="opportunity", cascade="all, delete-orphan"
    )
    sources: Mapped[List["OpportunitySource"]] = relationship(
        "OpportunitySource", back_populates="opportunity", cascade="all, delete-orphan", lazy="selectin"
    )
    verified_fields: Mapped[List["VerifiedField"]] = relationship(
        "VerifiedField", back_populates="opportunity", cascade="all, delete-orphan", lazy="selectin"
    )
    conflicts: Mapped[List["VerificationConflict"]] = relationship(
        "VerificationConflict", back_populates="opportunity", cascade="all, delete-orphan", lazy="selectin"
    )
    candidates_as_a: Mapped[List["SemanticMatchCandidate"]] = relationship(
        "SemanticMatchCandidate", foreign_keys="[SemanticMatchCandidate.opportunity_a_id]", back_populates="opportunity_a", cascade="all, delete-orphan"
    )
    candidates_as_b: Mapped[List["SemanticMatchCandidate"]] = relationship(
        "SemanticMatchCandidate", foreign_keys="[SemanticMatchCandidate.opportunity_b_id]", back_populates="opportunity_b", cascade="all, delete-orphan"
    )
    user_interactions: Mapped[List["UserOpportunityInteraction"]] = relationship(
        "UserOpportunityInteraction", back_populates="opportunity", cascade="all, delete-orphan"
    )
    # Relationships
    change_sets: Mapped[List["ChangeSet"]] = relationship(
        "ChangeSet", back_populates="opportunity", cascade="all, delete-orphan"
    )


    def __repr__(self) -> str:
        return f"<Opportunity id={self.id} title='{self.title[:30]}' category={self.category}>"
