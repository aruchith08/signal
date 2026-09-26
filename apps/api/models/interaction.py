"""
User Opportunity Interaction Model (Saved & Followed Opportunities)
"""
from typing import Optional
from sqlalchemy import Boolean, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from apps.api.database import Base
from apps.api.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class UserOpportunityInteraction(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Tracks per-user saved and followed states for opportunities.
    - Saved: bookmark for personal review
    - Followed: subscribe to future lifecycle and deadline alerts
    """
    __tablename__ = "user_opportunity_interactions"
    __table_args__ = (
        UniqueConstraint("user_id", "opportunity_id", name="uq_user_opportunity_interaction"),
    )

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    opportunity_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("opportunities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    is_saved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    is_followed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    user = relationship("User", back_populates="interactions")
    opportunity = relationship("Opportunity", back_populates="user_interactions")

    def __repr__(self) -> str:
        return f"<UserOpportunityInteraction user_id={self.user_id} opp_id={self.opportunity_id} saved={self.is_saved} followed={self.is_followed}>"
