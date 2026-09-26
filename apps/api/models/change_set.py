'''ChangeSet ORM Model - records field-level changes for opportunities'''

from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import DateTime, String, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from apps.api.database import Base
from apps.api.models.base import UUIDPrimaryKeyMixin, TimestampMixin
from shared.constants import ChangeType, PriorityLevel as ChangeImportance

if TYPE_CHECKING:
    from apps.api.models.opportunity import Opportunity
    from apps.api.models.snapshot import SourceSnapshot

class ChangeSet(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "change_sets"

    opportunity_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("opportunities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_discovery_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("source_snapshots.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    field_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    previous_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    new_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    change_type: Mapped[str] = mapped_column(
        String(50), default=ChangeType.NO_CHANGE.value, nullable=False, index=True
    )
    importance: Mapped[str] = mapped_column(
        String(20), default=ChangeImportance.MEDIUM.value, nullable=False, index=True
    )
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    resolved: Mapped[bool] = mapped_column(default=False, nullable=False)

    # Relationships
    opportunity: Mapped["Opportunity"] = relationship("Opportunity", back_populates="change_sets")
    source_snapshot: Mapped[Optional["SourceSnapshot"]] = relationship("SourceSnapshot", back_populates="change_sets")

    def __repr__(self) -> str:
        return (
            f"<ChangeSet id={self.id} opportunity_id={self.opportunity_id} "
            f"field={self.field_name} type={self.change_type} importance={self.importance}>"
        )
