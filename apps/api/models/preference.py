"""
UserNotificationPreference ORM Model — User alert settings, quiet hours, and Telegram binding
"""
from datetime import datetime
from typing import TYPE_CHECKING, Optional
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from apps.api.database import Base
from apps.api.models.base import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from apps.api.models.user import User


class UserNotificationPreference(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "user_notification_preferences"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    min_relevance_score: Mapped[int] = mapped_column(Integer, default=70, nullable=False)
    instant_alerts_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    digest_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    quiet_hours_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    quiet_hours_start: Mapped[str] = mapped_column(String(10), default="22:30", nullable=False)  # HH:MM format
    quiet_hours_end: Mapped[str] = mapped_column(String(10), default="07:30", nullable=False)    # HH:MM format
    timezone: Mapped[str] = mapped_column(String(50), default="Asia/Kolkata", nullable=False)
    max_alerts_per_day: Mapped[int] = mapped_column(Integer, default=10, nullable=False)

    # Telegram User Linking
    telegram_chat_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    telegram_user_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    telegram_username: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    telegram_linked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="preferences")

    def __repr__(self) -> str:
        return f"<UserNotificationPreference user_id={self.user_id} enabled={self.enabled} min_score={self.min_relevance_score}>"
