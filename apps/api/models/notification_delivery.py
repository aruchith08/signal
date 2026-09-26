'''NotificationDelivery ORM Model - tracks delivery attempts for notifications'''

from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, String, Text, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from apps.api.database import Base
from apps.api.models.base import UUIDPrimaryKeyMixin, TimestampMixin
from shared.constants import NotificationChannel, NotificationStatus

if TYPE_CHECKING:
    from apps.api.models.notification import Notification

class NotificationDelivery(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "notification_deliveries"

    notification_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("notifications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    channel: Mapped[str] = mapped_column(
        String(50), default=NotificationChannel.TELEGRAM.value, nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String(50), default=NotificationStatus.PENDING.value, nullable=False, index=True
    )
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_attempt_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Additional fields
    channel_identifier: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Relationship back to notification
    notification: Mapped["Notification"] = relationship("Notification", back_populates="deliveries")

    def __repr__(self) -> str:
        return f"<NotificationDelivery id={self.id} notification_id={self.notification_id} channel={self.channel} status={self.status}>"
