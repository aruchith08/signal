"""
Skill and UserSkill ORM Models — Flexible skill taxonomy and user skill assignments
"""
from typing import TYPE_CHECKING, Optional, List
from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from apps.api.database import Base
from apps.api.models.base import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from apps.api.models.user import User


class Skill(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "skills"

    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    category: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)

    # Relationships
    user_skills: Mapped[List["UserSkill"]] = relationship(
        "UserSkill", back_populates="skill", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Skill id={self.id} name='{self.name}'>"


class UserSkill(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "user_skills"
    __table_args__ = (
        UniqueConstraint("user_id", "skill_id", name="uq_user_skill"),
    )

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    skill_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("skills.id", ondelete="CASCADE"), nullable=False, index=True
    )
    proficiency_level: Mapped[str] = mapped_column(
        String(50), default="intermediate", nullable=False
    )  # beginner, intermediate, advanced, expert

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="skills")
    skill: Mapped["Skill"] = relationship("Skill", back_populates="user_skills", lazy="selectin")

    def __repr__(self) -> str:
        return f"<UserSkill user_id={self.user_id} skill_id={self.skill_id}>"
