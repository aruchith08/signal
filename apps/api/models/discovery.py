"""
RawDiscovery ORM Model — Full traceability and audit log for ingested internet content
"""
from datetime import datetime
from typing import Any, Dict, List, Optional, TYPE_CHECKING
from sqlalchemy import DateTime, ForeignKey, Index, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from apps.api.database import Base
from apps.api.models.base import TimestampMixin, UUIDPrimaryKeyMixin, utc_now
from shared.constants import DiscoveryStatus

if TYPE_CHECKING:
    from apps.api.models.source import Source
    from apps.api.models.opportunity import Opportunity
    from apps.api.models.event import OpportunityEvent
    from apps.api.models.program_watch import ProgramWatchMatch


class RawDiscovery(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "raw_discoveries"
    __table_args__ = (
        Index("uq_raw_discoveries_content_hash_canonical_url", "content_hash", "canonical_url", unique=True),
    )

    source_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("sources.id", ondelete="SET NULL"), nullable=True, index=True
    )
    external_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    original_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    canonical_url: Mapped[str] = mapped_column(String(1024), nullable=False, index=True)
    raw_title: Mapped[str] = mapped_column(String(512), nullable=False)
    raw_content: Mapped[str] = mapped_column(Text, nullable=False)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(50), default=DiscoveryStatus.DISCOVERED.value, nullable=False, index=True
    )
    content_classification: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    matched_by: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    processing_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    connector_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    opportunity_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("opportunities.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_event_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("opportunity_events.id", ondelete="SET NULL", use_alter=True, name="fk_raw_discoveries_created_event_id"), nullable=True, index=True
    )

    # Relationships
    source: Mapped[Optional["Source"]] = relationship("Source")
    opportunity: Mapped[Optional["Opportunity"]] = relationship("Opportunity")
    created_event: Mapped[Optional["OpportunityEvent"]] = relationship(
        "OpportunityEvent", foreign_keys=[created_event_id]
    )
    created_events: Mapped[List["OpportunityEvent"]] = relationship(
        "OpportunityEvent", foreign_keys="OpportunityEvent.source_discovery_id", back_populates="source_discovery"
    )
    watch_matches: Mapped[List["ProgramWatchMatch"]] = relationship(
        "ProgramWatchMatch", back_populates="raw_discovery", cascade="all, delete-orphan"
    )

    @property
    def metadata_json(self) -> Dict[str, Any]:
        """Convenience property returning connector_metadata as dict."""
        return self.connector_metadata or {}

    def __repr__(self) -> str:
        return f"<RawDiscovery id={self.id} title='{self.raw_title[:30]}' status={self.status}>"
