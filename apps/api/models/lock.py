"""
Distributed Lock ORM Model for multi-instance scheduler and ingestion coordination
"""
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from apps.api.database import Base
from apps.api.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class DistributedLock(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "distributed_locks"

    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    locked_by: Mapped[str] = mapped_column(String(100), nullable=False)
    acquired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    def is_expired(self, now: Optional[datetime] = None) -> bool:
        if now is None:
            now = datetime.now(timezone.utc)
        expires = self.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        return expires <= now

    def __repr__(self) -> str:
        return f"<DistributedLock name={self.name} locked_by={self.locked_by} expires_at={self.expires_at}>"
