"""
Source Snapshot ORM Model — Tracks point-in-time state of monitored sources
"""
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from apps.api.database import Base
from apps.api.models.base import TimestampMixin, UUIDPrimaryKeyMixin
from shared.constants import ChangeType

if TYPE_CHECKING:
    from apps.api.models.source import Source
    from apps.api.models.change_set import ChangeSet


class SourceSnapshot(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Stores a point-in-time snapshot of raw and normalized content from a source."""
    __tablename__ = "source_snapshots"

    source_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("sources.id", ondelete="CASCADE"), nullable=False, index=True
    )
    snapshot_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    normalized_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    raw_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    items_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="success", nullable=False)
    change_type: Mapped[Optional[str]] = mapped_column(
        String(50), default=ChangeType.NO_CHANGE.value, nullable=True
    )
    metadata_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    # Relationships
    source: Mapped["Source"] = relationship("Source", back_populates="snapshots")
    change_sets: Mapped[List["ChangeSet"]] = relationship(
        "ChangeSet", back_populates="source_snapshot"
    )

    def __repr__(self) -> str:
        return f"<SourceSnapshot id={self.id} source_id={self.source_id} hash={self.snapshot_hash[:8]}>"
