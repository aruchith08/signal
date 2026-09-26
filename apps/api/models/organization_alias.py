"""
Organization Alias ORM Model — Maps alternative names, acronyms, and aliases to canonical organizations
"""
from typing import TYPE_CHECKING
from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from apps.api.database import Base
from apps.api.models.base import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from apps.api.models.organization import Organization


class OrganizationAlias(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Tracks alternative names, acronyms, and nicknames for canonical organizations."""
    __tablename__ = "organization_aliases"
    __table_args__ = (
        UniqueConstraint("organization_id", "alias", name="uq_organization_alias"),
    )

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    alias: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_alias: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    # Relationships
    organization: Mapped["Organization"] = relationship("Organization", back_populates="aliases")

    def __repr__(self) -> str:
        return f"<OrganizationAlias {self.alias} -> org={self.organization_id}>"
