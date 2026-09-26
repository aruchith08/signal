"""
Source ORM Model
"""
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from apps.api.database import Base
from apps.api.models.base import TimestampMixin, UUIDPrimaryKeyMixin
from shared.constants import OpportunityCategory, SourceHealthStatus, SourceType, TrustLevel

if TYPE_CHECKING:
    from apps.api.models.organization import Organization
    from apps.api.models.opportunity import Opportunity
    from apps.api.models.snapshot import SourceSnapshot


class Source(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "sources"

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    organization_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True
    )
    category: Mapped[str] = mapped_column(
        String(50), default=OpportunityCategory.COMPETITIVE_PROGRAMMING.value, nullable=False, index=True
    )
    source_type: Mapped[str] = mapped_column(
        String(50), default=SourceType.API.value, nullable=False
    )
    base_url: Mapped[str] = mapped_column(String(1024), nullable=False, index=True)
    api_endpoint: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    monitor_frequency_minutes: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    trust_level: Mapped[str] = mapped_column(
        String(50), default=TrustLevel.HIGH.value, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    scheduler_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    last_polled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_successful_check: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    average_response_time: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(50), default=SourceHealthStatus.HEALTHY.value, nullable=False, index=True
    )
    polling_policy: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    priority_level: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    organization: Mapped[Optional["Organization"]] = relationship(
        "Organization", back_populates="sources"
    )
    opportunities: Mapped[List["Opportunity"]] = relationship(
        "Opportunity", back_populates="source"
    )
    snapshots: Mapped[List["SourceSnapshot"]] = relationship(
        "SourceSnapshot", back_populates="source", cascade="all, delete-orphan"
    )
    scheduled_jobs: Mapped[List["ScheduledJob"]] = relationship(
        "ScheduledJob", back_populates="source", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Source id={self.id} name={self.name} category={self.category}>"
