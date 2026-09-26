"""
Program Watch ORM Models — Explicit Monitored Programs, Aliases, Keywords, Sources, and Matches
"""
from datetime import datetime
from typing import Any, Dict, List, Optional, TYPE_CHECKING
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from apps.api.database import Base
from apps.api.models.base import TimestampMixin, UUIDPrimaryKeyMixin, utc_now
from shared.constants import WatchPriority

if TYPE_CHECKING:
    from apps.api.models.organization import Organization
    from apps.api.models.source import Source
    from apps.api.models.discovery import RawDiscovery


class ProgramWatch(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "program_watches"

    organization_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    canonical_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    priority: Mapped[str] = mapped_column(
        String(50), default=WatchPriority.HIGH.value, nullable=False, index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    # Relationships
    organization: Mapped[Optional["Organization"]] = relationship("Organization")
    aliases: Mapped[List["ProgramWatchAlias"]] = relationship(
        "ProgramWatchAlias",
        back_populates="program_watch",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    keywords: Mapped[List["ProgramWatchKeyword"]] = relationship(
        "ProgramWatchKeyword",
        back_populates="program_watch",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    sources: Mapped[List["ProgramWatchSource"]] = relationship(
        "ProgramWatchSource",
        back_populates="program_watch",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    matches: Mapped[List["ProgramWatchMatch"]] = relationship(
        "ProgramWatchMatch",
        back_populates="program_watch",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<ProgramWatch id={self.id} name='{self.name}' priority={self.priority} active={self.is_active}>"


class ProgramWatchAlias(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "program_watch_aliases"
    __table_args__ = (
        UniqueConstraint("program_watch_id", "normalized_alias", name="uq_program_watch_alias"),
    )

    program_watch_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("program_watches.id", ondelete="CASCADE"), nullable=False, index=True
    )
    alias: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_alias: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationships
    program_watch: Mapped["ProgramWatch"] = relationship("ProgramWatch", back_populates="aliases")

    def __repr__(self) -> str:
        return f"<ProgramWatchAlias id={self.id} alias='{self.alias}'>"


class ProgramWatchKeyword(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "program_watch_keywords"
    __table_args__ = (
        UniqueConstraint("program_watch_id", "normalized_keyword", name="uq_program_watch_keyword"),
    )

    program_watch_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("program_watches.id", ondelete="CASCADE"), nullable=False, index=True
    )
    keyword: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_keyword: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    weight: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    is_distinctive: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationships
    program_watch: Mapped["ProgramWatch"] = relationship("ProgramWatch", back_populates="keywords")

    def __repr__(self) -> str:
        return f"<ProgramWatchKeyword id={self.id} keyword='{self.keyword}' weight={self.weight}>"


class ProgramWatchSource(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "program_watch_sources"

    program_watch_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("program_watches.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("sources.id", ondelete="SET NULL"), nullable=True, index=True
    )
    url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    priority: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationships
    program_watch: Mapped["ProgramWatch"] = relationship("ProgramWatch", back_populates="sources")
    source: Mapped[Optional["Source"]] = relationship("Source")

    def __repr__(self) -> str:
        return f"<ProgramWatchSource id={self.id} watch_id={self.program_watch_id} active={self.is_active}>"


class ProgramWatchMatch(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "program_watch_matches"
    __table_args__ = (
        UniqueConstraint("program_watch_id", "raw_discovery_id", name="uq_program_watch_raw_discovery_match"),
    )

    program_watch_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("program_watches.id", ondelete="CASCADE"), nullable=False, index=True
    )
    raw_discovery_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("raw_discoveries.id", ondelete="CASCADE"), nullable=False, index=True
    )
    match_score: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    match_level: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    match_reason: Mapped[str] = mapped_column(Text, nullable=False)
    matched_terms: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationships
    program_watch: Mapped["ProgramWatch"] = relationship("ProgramWatch", back_populates="matches")
    raw_discovery: Mapped["RawDiscovery"] = relationship("RawDiscovery", back_populates="watch_matches")

    def __repr__(self) -> str:
        return f"<ProgramWatchMatch id={self.id} watch_id={self.program_watch_id} score={self.match_score:.2f} level={self.match_level}>"
