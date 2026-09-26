"""
User, UserProfile, and UserInterest ORM Models
"""
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from apps.api.database import Base
from apps.api.models.base import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from apps.api.models.notification import Notification
    from apps.api.models.skill import UserSkill
    from apps.api.models.preference import UserNotificationPreference
    from apps.api.models.interaction import UserOpportunityInteraction


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    full_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    hashed_password: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    role: Mapped[str] = mapped_column(String(50), default="user", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    profile: Mapped[Optional["UserProfile"]] = relationship(
        "UserProfile", back_populates="user", uselist=False, cascade="all, delete-orphan", lazy="selectin"
    )
    preferences: Mapped[Optional["UserNotificationPreference"]] = relationship(
        "UserNotificationPreference", back_populates="user", uselist=False, cascade="all, delete-orphan", lazy="selectin"
    )
    interests: Mapped[List["UserInterest"]] = relationship(
        "UserInterest", back_populates="user", cascade="all, delete-orphan", lazy="selectin"
    )
    skills: Mapped[List["UserSkill"]] = relationship(
        "UserSkill", back_populates="user", cascade="all, delete-orphan", lazy="selectin"
    )
    notifications: Mapped[List["Notification"]] = relationship(
        "Notification", back_populates="user", cascade="all, delete-orphan"
    )
    interactions: Mapped[List["UserOpportunityInteraction"]] = relationship(
        "UserOpportunityInteraction", back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} username={self.username}>"


class UserProfile(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "user_profiles"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True
    )
    education_level: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # e.g., Undergraduate
    degree: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)           # e.g., B.Tech
    branch: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)           # e.g., CSE / AIML
    current_year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)         # e.g., 2
    graduation_year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)      # e.g., 2026
    country: Mapped[str] = mapped_column(String(100), default="India", nullable=False)
    state: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    timezone: Mapped[str] = mapped_column(String(50), default="Asia/Kolkata", nullable=False)
    career_interests: Mapped[Optional[str]] = mapped_column(Text, nullable=True)        # comma-separated or text
    preferred_opportunity_types: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # comma-separated
    bio: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="profile")

    def __repr__(self) -> str:
        return f"<UserProfile user_id={self.user_id} degree={self.degree}>"


class UserInterest(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "user_interests"
    __table_args__ = (
        UniqueConstraint("user_id", "category", "tag", name="uq_user_interest_tag"),
    )

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    tag: Mapped[str] = mapped_column(String(100), nullable=False)
    weight: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)  # 0.0 - 1.0 relevance scale

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="interests")

    def __repr__(self) -> str:
        return f"<UserInterest user_id={self.user_id} tag={self.tag}>"
