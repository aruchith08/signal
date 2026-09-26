"""
Program Watch Engine — Coordinates active watch loading, discovery evaluation, and idempotent match persistence
"""
import logging
import re
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import or_, select
from sqlalchemy.orm import selectinload

from apps.api.models.discovery import RawDiscovery
from apps.api.models.program_watch import (
    ProgramWatch,
    ProgramWatchAlias,
    ProgramWatchKeyword,
    ProgramWatchMatch,
    ProgramWatchSource,
)
from services.watch.matcher import ProgramWatchMatcher, WatchMatchResult
from services.watch.scoring import WatchMatchScorer
from shared.constants import WatchPriority

logger = logging.getLogger("signal.watch.engine")


class ProgramWatchEngine:
    """
    Evaluates raw discoveries against all active ProgramWatch configurations.
    Persists explainable evidence records in program_watch_matches.
    Guarantees:
      - Only active watches participate.
      - One discovery can match multiple distinct watches.
      - Duplicate matches on repeated polls are strictly prevented (idempotent).
      - Fault-tolerant: errors in watch evaluation never abort discovery ingestion.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def load_active_watches(
        self,
        discovery: Optional[RawDiscovery] = None,
        limit: Optional[int] = None,
    ) -> List[ProgramWatch]:
        """
        Load active program watches with relationships pre-fetched.
        If discovery is provided, applies database-level pre-filtering by source_id,
        title keywords, and aliases to scale efficiently with large watch catalogs.
        """
        base_query = (
            select(ProgramWatch)
            .where(ProgramWatch.is_active.is_(True))
            .options(
                selectinload(ProgramWatch.aliases),
                selectinload(ProgramWatch.keywords),
                selectinload(ProgramWatch.sources),
                selectinload(ProgramWatch.organization),
            )
        )

        if discovery is not None:
            conditions = []

            # 1. Source association pre-filter
            if discovery.source_id:
                conditions.append(
                    ProgramWatch.sources.any(ProgramWatchSource.source_id == discovery.source_id)
                )

            # 2. Extract significant tokens from discovery title
            title = discovery.raw_title or ""
            words = [w.strip() for w in re.split(r"[\s\-_:,|]+", title) if len(w.strip()) >= 3]
            stop_words = {"the", "and", "for", "with", "from", "2024", "2025", "2026", "new", "live", "open"}
            sig_words = [w for w in words if w.lower() not in stop_words][:6]

            for word in sig_words:
                pattern = f"%{word}%"
                conditions.append(ProgramWatch.name.ilike(pattern))
                conditions.append(ProgramWatch.canonical_name.ilike(pattern))
                conditions.append(ProgramWatch.aliases.any(ProgramWatchAlias.alias.ilike(pattern)))
                conditions.append(ProgramWatch.keywords.any(ProgramWatchKeyword.keyword.ilike(pattern)))

            # Critical priority watches are always included in candidate set
            conditions.append(ProgramWatch.priority == WatchPriority.CRITICAL.value)

            if conditions:
                base_query = base_query.where(or_(*conditions))

        if limit:
            base_query = base_query.limit(limit)

        result = await self.db.execute(base_query)
        return list(result.scalars().all())

    async def evaluate_discovery(self, discovery: RawDiscovery) -> List[ProgramWatchMatch]:
        """
        Evaluate discovery against candidate active watches.
        Records and returns any ProgramWatchMatch instances created or existing.
        """
        matches_found: List[ProgramWatchMatch] = []
        if not discovery or not discovery.id:
            return matches_found

        try:
            active_watches = await self.load_active_watches(discovery=discovery)
            if not active_watches:
                return matches_found

            for watch in active_watches:
                try:
                    result: WatchMatchResult = ProgramWatchMatcher.match(discovery, watch)
                    if result.matched and WatchMatchScorer.is_actionable(result.score):
                        # Idempotency check: see if match already recorded
                        existing_stmt = select(ProgramWatchMatch).where(
                            ProgramWatchMatch.program_watch_id == watch.id,
                            ProgramWatchMatch.raw_discovery_id == discovery.id,
                        )
                        existing_match = (await self.db.execute(existing_stmt)).scalars().first()

                        if existing_match:
                            logger.debug(
                                f"[WatchEngine] Match already exists for watch '{watch.name}' "
                                f"and discovery '{discovery.id}'"
                            )
                            matches_found.append(existing_match)
                        else:
                            new_match = ProgramWatchMatch(
                                program_watch_id=watch.id,
                                raw_discovery_id=discovery.id,
                                match_score=result.score,
                                match_level=result.match_level.value if result.match_level else "unknown",
                                match_reason=result.match_reason,
                                matched_terms=result.matched_terms,
                            )
                            self.db.add(new_match)
                            await self.db.flush()
                            matches_found.append(new_match)
                            logger.info(
                                f"[WatchEngine] ⭐ MATCH DETECTED for '{watch.name}' "
                                f"(Score: {result.score:.2f}, Level: {result.match_level.value}) "
                                f"Discovery: '{discovery.raw_title}'"
                            )
                except Exception as e:
                    # Log error for individual watch without failing entire evaluation
                    logger.warning(
                        f"[WatchEngine] Error evaluating watch '{watch.name}' for discovery '{discovery.id}': {e}",
                        exc_info=True,
                    )

        except Exception as e:
            # Fatal error guardrail: ingestion must never be blocked if the watch engine encounters an issue
            logger.error(f"[WatchEngine] Failed to evaluate watches for discovery '{discovery.id}': {e}", exc_info=True)

        return matches_found
