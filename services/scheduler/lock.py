"""
Database-Backed Distributed Lock for Multi-Instance Production Safety
Prevents concurrent execution of scheduler polling, ingestion, and background jobs.
"""
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
import logging
import os
import socket
from typing import AsyncGenerator, Optional
import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.models.lock import DistributedLock

logger = logging.getLogger("signal.scheduler.lock")


class DistributedLockManager:
    """
    Manages database-backed distributed leases across multiple API instances and worker processes.
    Self-healing: expired locks left by crashed processes are automatically reclaimed.
    """

    def __init__(self, db: AsyncSession, instance_id: Optional[str] = None):
        self.db = db
        if instance_id:
            self.instance_id = instance_id
        else:
            hostname = socket.gethostname() or "node"
            pid = os.getpid()
            rand = uuid.uuid4().hex[:6]
            self.instance_id = f"{hostname}:{pid}:{rand}"

    async def acquire(
        self,
        lock_name: str,
        timeout_seconds: int = 300,
        owner_id: Optional[str] = None,
    ) -> bool:
        """
        Attempt to acquire a distributed lock.
        Returns True if acquired; False if currently held by another live process.
        """
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=timeout_seconds)
        owner = owner_id or self.instance_id

        try:
            stmt = select(DistributedLock).where(DistributedLock.name == lock_name)
            result = await self.db.execute(stmt)
            lock = result.scalars().first()

            if lock is None:
                new_lock = DistributedLock(
                    name=lock_name,
                    locked_by=owner,
                    acquired_at=now,
                    expires_at=expires_at,
                )
                self.db.add(new_lock)
                await self.db.commit()
                logger.info(f"[Lock] Acquired new lock '{lock_name}' by '{owner}' (expires in {timeout_seconds}s)")
                return True

            # Check if lock has expired (reclaim from dead worker)
            if lock.is_expired(now):
                previous_owner = lock.locked_by
                lock.locked_by = owner
                lock.acquired_at = now
                lock.expires_at = expires_at
                await self.db.commit()
                logger.warning(
                    f"[Lock] Reclaimed expired lock '{lock_name}' from '{previous_owner}' "
                    f"by '{owner}' (expires in {timeout_seconds}s)"
                )
                return True

            # If current instance already owns it, extend lease
            if lock.locked_by == owner:
                lock.expires_at = expires_at
                await self.db.commit()
                return True

            # Held by another live process
            logger.debug(
                f"[Lock] Lock '{lock_name}' is currently held by '{lock.locked_by}' "
                f"until {lock.expires_at.isoformat()}"
            )
            return False

        except IntegrityError:
            # Race condition: another instance inserted the lock row concurrently
            await self.db.rollback()
            logger.debug(f"[Lock] Race condition acquiring '{lock_name}'; lock conceded to peer")
            return False
        except Exception as exc:
            await self.db.rollback()
            logger.error(f"[Lock] Unexpected error acquiring lock '{lock_name}': {exc}", exc_info=True)
            return False

    async def release(self, lock_name: str, owner_id: Optional[str] = None) -> bool:
        """
        Release a distributed lock if owned by the caller.
        """
        owner = owner_id or self.instance_id
        try:
            stmt = select(DistributedLock).where(DistributedLock.name == lock_name)
            result = await self.db.execute(stmt)
            lock = result.scalars().first()

            if lock and lock.locked_by == owner:
                await self.db.delete(lock)
                await self.db.commit()
                logger.info(f"[Lock] Released lock '{lock_name}' by '{owner}'")
                return True
            return False
        except Exception as exc:
            await self.db.rollback()
            logger.warning(f"[Lock] Error releasing lock '{lock_name}': {exc}")
            return False

    @asynccontextmanager
    async def hold(
        self,
        lock_name: str,
        timeout_seconds: int = 300,
        owner_id: Optional[str] = None,
    ) -> AsyncGenerator[bool, None]:
        """
        Context manager for acquiring and safely auto-releasing a distributed lock.
        Yields True if lock acquired, False otherwise.
        """
        owner = owner_id or self.instance_id
        acquired = await self.acquire(lock_name, timeout_seconds=timeout_seconds, owner_id=owner)
        try:
            yield acquired
        finally:
            if acquired:
                await self.release(lock_name, owner_id=owner)
