"""
Notification ORM Model — Multi-channel notification audit log
"""
from datetime import datetime
from typing import TYPE_CHECKING, Optional, List
from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from apps.api.database import Base
from apps.api.models.base import TimestampMixin, UUIDPrimaryKeyMixin
from shared.constants import NotificationChannel, NotificationStatus, PriorityLevel, UserNotificationStatus

if TYPE_CHECKING:
    from apps.api.models.user import User
    from apps.api.models.opportunity import Opportunity
    from apps.api.models.event import OpportunityEvent


class Notification(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "notifications"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    opportunity_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("opportunities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("opportunity_events.id", ondelete="SET NULL"), nullable=True, index=True
    )
    channel: Mapped[str] = mapped_column(
        String(50), default=NotificationChannel.TELEGRAM.value, nullable=False
    )
    priority: Mapped[str] = mapped_column(
        String(50), default=PriorityLevel.MEDIUM.value, nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String(50), default=NotificationStatus.PENDING.value, nullable=False, index=True
    )
    delivery_mode: Mapped[str] = mapped_column(
        String(50), default="instant", nullable=False
    )
    relevance_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    decision_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    dismissed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    # user-visible status (UNREAD, READ, DISMISSED)
    user_status: Mapped[str] = mapped_column(String(20), default=UserNotificationStatus.UNREAD.value, nullable=False, index=True)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="notifications")
    opportunity: Mapped["Opportunity"] = relationship("Opportunity", back_populates="notifications")
    event: Mapped[Optional["OpportunityEvent"]] = relationship(
        "OpportunityEvent", back_populates="notifications"
    )
    deliveries: Mapped[List["NotificationDelivery"]] = relationship(
        "NotificationDelivery", back_populates="notification", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Notification id={self.id} user={self.user_id} channel={self.channel} status={self.status}>"
