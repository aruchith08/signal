"""
OpportunityAlias ORM Model — Known aliases and title variations for entity resolution
"""
from typing import TYPE_CHECKING, Optional
from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from apps.api.database import Base
from apps.api.models.base import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from apps.api.models.opportunity import Opportunity


class OpportunityAlias(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "opportunity_aliases"

    opportunity_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("opportunities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    alias: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    source: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Relationships
    opportunity: Mapped["Opportunity"] = relationship("Opportunity", back_populates="aliases")

    def __repr__(self) -> str:
        return f"<OpportunityAlias id={self.id} opp_id={self.opportunity_id} alias='{self.alias}'>"
