"""
OpportunityEvent ORM Model — Lifecycle events associated with opportunities
"""
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from apps.api.database import Base
from apps.api.models.base import TimestampMixin, UUIDPrimaryKeyMixin
from shared.constants import EventType

if TYPE_CHECKING:
    from apps.api.models.opportunity import Opportunity
    from apps.api.models.notification import Notification
    from apps.api.models.discovery import RawDiscovery


class OpportunityEvent(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "opportunity_events"
    __table_args__ = (
        Index("uq_opportunity_events_opp_content_hash", "opportunity_id", "content_hash", unique=True),
    )

    opportunity_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("opportunities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_discovery_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("raw_discoveries.id", ondelete="SET NULL"), nullable=True, index=True
    )
    event_type: Mapped[str] = mapped_column(
        String(50), default=EventType.ANNOUNCEMENT.value, nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    event_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    deadline_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    is_critical: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    content_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    source_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)

    # Relationships
    opportunity: Mapped["Opportunity"] = relationship("Opportunity", back_populates="events")
    source_discovery: Mapped[Optional["RawDiscovery"]] = relationship(
        "RawDiscovery", foreign_keys=[source_discovery_id], back_populates="created_events"
    )
    notifications: Mapped[List["Notification"]] = relationship(
        "Notification", back_populates="event", cascade="all, delete-orphan"
    )


    def __repr__(self) -> str:
        return f"<OpportunityEvent id={self.id} type={self.event_type} date={self.event_date}>"
