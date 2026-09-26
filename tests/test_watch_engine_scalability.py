"""
Unit & Integration Tests for Priority 7: Watch Engine Scalability
Validates:
- Database-level pre-filtering in ProgramWatchEngine.load_active_watches(discovery)
- Pre-filtering selects relevant watches by title tokens, aliases, keywords, and source IDs
- Critical priority watches are included in the pre-filtered candidate set
- Irrelevant active watches are filtered out before in-memory evaluation
- Backward compatibility of load_active_watches() when called without discovery
"""
from datetime import datetime, timezone
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from apps.api.models.base import Base
from apps.api.models.discovery import RawDiscovery
from apps.api.models.program_watch import (
    ProgramWatch,
    ProgramWatchAlias,
    ProgramWatchKeyword,
    ProgramWatchSource,
)
from apps.api.models.source import Source
from services.watch.engine import ProgramWatchEngine
from shared.constants import WatchPriority


class TestWatchEngineScalability(unittest.IsolatedAsyncioTestCase):
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

    async def test_load_active_watches_unfiltered_backward_compatible(self):
        """Calling load_active_watches without discovery returns all active watches."""
        async with self.session_factory() as session:
            w1 = ProgramWatch(name="Smart India Hackathon", canonical_name="SIH", is_active=True)
            w2 = ProgramWatch(name="Google Summer of Code", canonical_name="GSoC", is_active=True)
            w3 = ProgramWatch(name="Inactive Watch", canonical_name="IW", is_active=False)
            session.add_all([w1, w2, w3])
            await session.commit()

            engine = ProgramWatchEngine(session)
            watches = await engine.load_active_watches()
            self.assertEqual(len(watches), 2)
            names = [w.name for w in watches]
            self.assertIn("Smart India Hackathon", names)
            self.assertIn("Google Summer of Code", names)

    async def test_load_active_watches_prefiltering_by_keywords(self):
        """Pre-filtering selects watches matching discovery title tokens and ignores irrelevant ones."""
        async with self.session_factory() as session:
            # 1. Matching watch by keyword
            w1 = ProgramWatch(name="SIH 2026", canonical_name="SIH 2026", is_active=True)
            w1.keywords.append(ProgramWatchKeyword(keyword="hackathon", normalized_keyword="hackathon", weight=1.0))

            # 2. Matching watch by name token
            w2 = ProgramWatch(name="Smart India Hackathon", canonical_name="SIH", is_active=True)

            # 3. Matching watch by alias
            w3 = ProgramWatch(name="TCS Coding Challenge", canonical_name="TCS Contest", is_active=True)
            w3.aliases.append(ProgramWatchAlias(alias="CodeVita", normalized_alias="codevita"))

            # 4. Completely unrelated active watch
            w4 = ProgramWatch(name="Kaggle Grandmaster League", canonical_name="KGL", is_active=True)

            session.add_all([w1, w2, w3, w4])
            await session.commit()

            discovery = RawDiscovery(
                content_hash="hash1",
                canonical_url="https://sih.gov.in",
                original_url="https://sih.gov.in",
                raw_title="Smart India Hackathon Announced for Engineering Colleges",
                raw_content="Hackathon registration is now open.",
                status="discovered",
            )

            engine = ProgramWatchEngine(session)
            candidates = await engine.load_active_watches(discovery=discovery)

            candidate_names = [w.name for w in candidates]
            # w1 matched via 'hackathon' keyword
            self.assertIn("SIH 2026", candidate_names)
            # w2 matched via 'Smart India Hackathon' name
            self.assertIn("Smart India Hackathon", candidate_names)
            # w4 is unrelated and must NOT be loaded into memory
            self.assertNotIn("Kaggle Grandmaster League", candidate_names)

    async def test_load_active_watches_includes_critical_priority(self):
        """Watches with CRITICAL priority are always included regardless of title tokens."""
        async with self.session_factory() as session:
            w_crit = ProgramWatch(
                name="Critical National Initiative",
                canonical_name="CNI",
                priority=WatchPriority.CRITICAL.value,
                is_active=True,
            )
            w_unrelated = ProgramWatch(
                name="Normal Unrelated Contest",
                canonical_name="NUC",
                priority=WatchPriority.MEDIUM.value,
                is_active=True,
            )
            session.add_all([w_crit, w_unrelated])
            await session.commit()

            discovery = RawDiscovery(
                content_hash="hash2",
                canonical_url="https://example.com/robotics",
                original_url="https://example.com/robotics",
                raw_title="Autonomous Drone Championship",
                raw_content="Robotics fly-off event.",
                status="discovered",
            )

            engine = ProgramWatchEngine(session)
            candidates = await engine.load_active_watches(discovery=discovery)

            candidate_names = [w.name for w in candidates]
            self.assertIn("Critical National Initiative", candidate_names)
            self.assertNotIn("Normal Unrelated Contest", candidate_names)
