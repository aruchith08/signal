"""
Codeforces Live Source Connector
Fetches competitive programming contests from the official Codeforces REST API.
"""
from datetime import datetime, timezone
import logging
from typing import List, Optional
from connectors.base_connector import BaseConnector, RawItem
from services.ingestion.http_client import ResilientHTTPClient
from shared.constants import OpportunityCategory, SourceType, TrustLevel

logger = logging.getLogger("signal.connectors.codeforces")

CODEFORCES_API_URL = "https://codeforces.com/api/contest.list?gym=false"


class CodeforcesConnector(BaseConnector):
    """Live connector for Codeforces competitive programming contests."""

    def __init__(
        self,
        api_url: str = CODEFORCES_API_URL,
        include_recent_finished: int = 10,
        is_active: bool = True,
    ):
        super().__init__(
            name="Codeforces",
            category=OpportunityCategory.COMPETITIVE_PROGRAMMING,
            source_type=SourceType.API,
            trust_level=TrustLevel.HIGHEST,
            base_url="https://codeforces.com",
            is_active=is_active,
        )

        self.api_url = api_url
        self.include_recent_finished = include_recent_finished

    async def health_check(self) -> bool:
        """Verify Codeforces API responsiveness."""
        try:
            async with ResilientHTTPClient(timeout=10.0) as client:
                res = await client.get(self.api_url)
                data = res.json()
                return res.status_code == 200 and data.get("status") == "OK"
        except Exception as exc:
            logger.warning(f"[CodeforcesConnector] Health check failed: {exc}")
            return False

    async def fetch_raw_items(self) -> List[RawItem]:
        """Fetch upcoming and recently completed Codeforces contests."""
        async with ResilientHTTPClient(timeout=15.0) as client:
            response = await client.get(self.api_url)
            payload = response.json()

        if payload.get("status") != "OK":
            raise ValueError(f"Codeforces API error: {payload.get('comment', 'Unknown error')}")

        contests = payload.get("result", [])
        raw_items: List[RawItem] = []

        upcoming: List[dict] = []
        recent_finished: List[dict] = []

        for c in contests:
            phase = c.get("phase")
            if phase in ["BEFORE", "CODING"]:
                upcoming.append(c)
            elif phase == "FINISHED":
                if len(recent_finished) < self.include_recent_finished:
                    recent_finished.append(c)

        # Process upcoming first, then recent finished
        selected_contests = upcoming + recent_finished

        for c in selected_contests:
            contest_id = c["id"]
            name = c.get("name", f"Codeforces Contest {contest_id}")
            phase = c.get("phase", "UNKNOWN")
            duration_secs = c.get("durationSeconds", 7200)
            duration_hours = duration_secs / 3600.0
            start_time_secs = c.get("startTimeSeconds")

            start_dt: Optional[datetime] = None
            if start_time_secs:
                start_dt = datetime.fromtimestamp(start_time_secs, tz=timezone.utc)

            url = f"https://codeforces.com/contest/{contest_id}"
            
            # Format informative content for matching & extraction
            start_str = start_dt.strftime("%Y-%m-%d %H:%M UTC") if start_dt else "TBD"
            content = (
                f"Codeforces Contest: {name}\n"
                f"Status/Phase: {phase}\n"
                f"Start Time: {start_str}\n"
                f"Duration: {duration_hours:.1f} hours ({duration_secs} seconds)\n"
                f"Contest Type: {c.get('type', 'CF')}\n"
                f"Registration and Contest Details: {url}\n"
                f"Compete online with programmers worldwide to solve algorithmic coding challenges, "
                f"gain rating points, and showcase problem-solving skills."
            )

            raw_item = RawItem(
                title=name,
                url=url,
                content=content,
                source_name=self.name,
                source_identifier=str(contest_id),
                published_at=start_dt,
                metadata={
                    "contest_id": contest_id,
                    "phase": phase,
                    "type": c.get("type"),
                    "duration_seconds": duration_secs,
                    "start_time_seconds": start_time_secs,
                    "relative_time_seconds": c.get("relativeTimeSeconds"),
                },
            )
            raw_items.append(raw_item)

        logger.info(f"[CodeforcesConnector] Fetched {len(raw_items)} contests ({len(upcoming)} upcoming, {len(recent_finished)} recent finished)")
        return raw_items
