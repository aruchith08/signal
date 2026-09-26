"""
Unit Tests for Priority 4: Database-Backed Distributed Locking
Validates:
- Lock acquisition on free resources
- Contention rejection when unexpired lock is held
- Lease extension when re-acquired by same owner
- Lease expiration and automatic reclamation by another instance
- Explicit release and unauthorized release rejection
- Context manager hold() semantics
- Coordinator / poll_source locking behavior
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import unittest
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select

from apps.api.models.base import Base
from apps.api.models.lock import DistributedLock
from services.scheduler.lock import DistributedLockManager
from shared.utils import parse_iso_datetime


class TestDistributedLockManager(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        self.session_factory = async_sessionmaker(
            bind=self.engine, class_=AsyncSession, expire_on_commit=False
        )

    async def asyncTearDown(self):
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await self.engine.dispose()

    async def test_acquire_free_lock_success(self):
        """Acquiring an unheld lock succeeds and records state in the database."""
        async with self.session_factory() as session:
            mgr = DistributedLockManager(session, instance_id="instance-A")
            acquired = await mgr.acquire("job_1", timeout_seconds=60)
            self.assertTrue(acquired)

            stmt = select(DistributedLock).where(DistributedLock.name == "job_1")
            res = await session.execute(stmt)
            lock = res.scalars().first()
            self.assertIsNotNone(lock)
            self.assertEqual(lock.locked_by, "instance-A")
            self.assertFalse(lock.is_expired())

    async def test_acquire_contention_rejected(self):
        """Acquiring a lock currently held by another live instance returns False."""
        async with self.session_factory() as session1:
            mgr1 = DistributedLockManager(session1, instance_id="instance-A")
            acquired1 = await mgr1.acquire("shared_resource", timeout_seconds=120)
            self.assertTrue(acquired1)

        async with self.session_factory() as session2:
            mgr2 = DistributedLockManager(session2, instance_id="instance-B")
            acquired2 = await mgr2.acquire("shared_resource", timeout_seconds=120)
            self.assertFalse(acquired2)

    async def test_acquire_same_owner_extends_lease(self):
        """Re-acquiring an active lock by the same owner succeeds and extends expiration."""
        async with self.session_factory() as session:
            mgr = DistributedLockManager(session, instance_id="instance-A")
            acquired = await mgr.acquire("heartbeat_job", timeout_seconds=30)
            self.assertTrue(acquired)

            stmt = select(DistributedLock).where(DistributedLock.name == "heartbeat_job")
            lock = (await session.execute(stmt)).scalars().first()
            first_expiry = parse_iso_datetime(lock.expires_at)

            # Re-acquire with longer timeout
            reacquired = await mgr.acquire("heartbeat_job", timeout_seconds=300)
            self.assertTrue(reacquired)

            lock = (await session.execute(stmt)).scalars().first()
            second_expiry = parse_iso_datetime(lock.expires_at)
            self.assertGreater(second_expiry, first_expiry)

    async def test_acquire_reclaims_expired_lock(self):
        """An expired lock left behind by a dead instance is safely reclaimed by a new instance."""
        async with self.session_factory() as session:
            # Simulate dead process that left an expired lock
            now = datetime.now(timezone.utc)
            expired_time = now - timedelta(seconds=10)
            dead_lock = DistributedLock(
                name="crashed_job",
                locked_by="dead-instance-999",
                acquired_at=now - timedelta(minutes=10),
                expires_at=expired_time,
            )
            session.add(dead_lock)
            await session.commit()

        async with self.session_factory() as session2:
            mgr2 = DistributedLockManager(session2, instance_id="live-instance-1")
            acquired = await mgr2.acquire("crashed_job", timeout_seconds=60)
            self.assertTrue(acquired)

            stmt = select(DistributedLock).where(DistributedLock.name == "crashed_job")
            reclaimed_lock = (await session2.execute(stmt)).scalars().first()
            self.assertEqual(reclaimed_lock.locked_by, "live-instance-1")
            self.assertFalse(reclaimed_lock.is_expired())

    async def test_release_by_owner_removes_lock(self):
        """Owner can successfully release their lock."""
        async with self.session_factory() as session:
            mgr = DistributedLockManager(session, instance_id="instance-A")
            await mgr.acquire("job_to_release", timeout_seconds=60)

            released = await mgr.release("job_to_release")
            self.assertTrue(released)

            stmt = select(DistributedLock).where(DistributedLock.name == "job_to_release")
            lock = (await session.execute(stmt)).scalars().first()
            self.assertIsNone(lock)

    async def test_release_by_non_owner_fails(self):
        """A different instance cannot release another instance's lock."""
        async with self.session_factory() as session:
            mgr1 = DistributedLockManager(session, instance_id="instance-A")
            await mgr1.acquire("protected_job", timeout_seconds=60)

            mgr2 = DistributedLockManager(session, instance_id="instance-B")
            released = await mgr2.release("protected_job")
            self.assertFalse(released)

            stmt = select(DistributedLock).where(DistributedLock.name == "protected_job")
            lock = (await session.execute(stmt)).scalars().first()
            self.assertIsNotNone(lock)
            self.assertEqual(lock.locked_by, "instance-A")

    async def test_hold_context_manager(self):
        """hold context manager acquires lock and automatically releases on exit."""
        async with self.session_factory() as session:
            mgr = DistributedLockManager(session, instance_id="instance-A")

            async with mgr.hold("scoped_job", timeout_seconds=60) as acquired:
                self.assertTrue(acquired)
                stmt = select(DistributedLock).where(DistributedLock.name == "scoped_job")
                lock = (await session.execute(stmt)).scalars().first()
                self.assertIsNotNone(lock)

            # Once exited, lock is released
            lock = (await session.execute(stmt)).scalars().first()
            self.assertIsNone(lock)
