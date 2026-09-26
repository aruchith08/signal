"""ScheduledJob ORM Model - audit of scheduler executions"""

from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import DateTime, Integer, String, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from apps.api.database import Base
from apps.api.models.base import UUIDPrimaryKeyMixin, TimestampMixin
from shared.constants import ScheduledJobStatus

if TYPE_CHECKING:
    from apps.api.models.source import Source


class ScheduledJob(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "scheduled_jobs"

    source_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20),
        default=ScheduledJobStatus.PENDING.value,
        nullable=False,
        index=True,
    )
    items_discovered: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    items_processed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Relationship back to source
    source: Mapped["Source"] = relationship("Source", back_populates="scheduled_jobs")

    def __repr__(self) -> str:
        return f"<ScheduledJob id={self.id} source_id={self.source_id} status={self.status}>"
