"""
LeetCode Live Source Connector
Fetches official weekly and biweekly contests from LeetCode's public GraphQL endpoint.
"""
from datetime import datetime, timezone
import logging
import time
from typing import List, Optional
from connectors.base_connector import BaseConnector, RawItem
from services.ingestion.http_client import ResilientHTTPClient
from shared.constants import OpportunityCategory, SourceType, TrustLevel

logger = logging.getLogger("signal.connectors.leetcode")

LEETCODE_GRAPHQL_URL = "https://leetcode.com/graphql"
LEETCODE_QUERY = """
query {
    allContests {
        title
        titleSlug
        startTime
        duration
    }
}
"""


class LeetCodeConnector(BaseConnector):
    """Live connector for LeetCode weekly and biweekly contests."""

    def __init__(
        self,
        graphql_url: str = LEETCODE_GRAPHQL_URL,
        lookback_days: int = 14,
        is_active: bool = True,
    ):
        super().__init__(
            name="LeetCode",
            category=OpportunityCategory.COMPETITIVE_PROGRAMMING,
            source_type=SourceType.API,
            trust_level=TrustLevel.HIGH,
            base_url="https://leetcode.com",
            is_active=is_active,
        )
        self.graphql_url = graphql_url
        self.lookback_days = lookback_days

    async def health_check(self) -> bool:
        """Verify LeetCode GraphQL responsiveness."""
        try:
            async with ResilientHTTPClient(timeout=10.0) as client:
                res = await client.post(
                    self.graphql_url,
                    json={"query": "{ allContests { title titleSlug } }"},
                    headers={"Content-Type": "application/json"},
                )
                if res.status_code != 200:
                    return False
                data = res.json()
                return "allContests" in data.get("data", {})
        except Exception as exc:
            logger.warning(f"[LeetCodeConnector] Health check failed: {exc}")
            return False

    async def fetch_raw_items(self) -> List[RawItem]:
        """Fetch upcoming and recent LeetCode contests."""
        async with ResilientHTTPClient(timeout=15.0) as client:
            response = await client.post(
                self.graphql_url,
                json={"query": LEETCODE_QUERY},
                headers={"Content-Type": "application/json"},
            )
            payload = response.json()

        all_contests = payload.get("data", {}).get("allContests", [])
        now_ts = time.time()
        cutoff_ts = now_ts - (self.lookback_days * 86400)

        # Filter for recent or upcoming contests
        recent_and_upcoming = [
            c for c in all_contests
            if c.get("startTime", 0) >= cutoff_ts
        ]
        recent_and_upcoming.sort(key=lambda c: c.get("startTime", 0))

        raw_items: List[RawItem] = []
        for c in recent_and_upcoming:
            title = c.get("title", "").strip()
            slug = c.get("titleSlug", "").strip()
            start_ts = c.get("startTime", 0)
            duration_secs = c.get("duration", 5400)

            if not title or not slug:
                continue

            start_dt = datetime.fromtimestamp(start_ts, tz=timezone.utc)
            end_dt = datetime.fromtimestamp(start_ts + duration_secs, tz=timezone.utc)

            url = f"https://leetcode.com/contest/{slug}"
            start_str = start_dt.strftime("%d %B %Y %H:%M UTC")
            end_str = end_dt.strftime("%d %B %Y %H:%M UTC")

            content = (
                f"LeetCode Contest: {title}\n"
                f"Starts: {start_str}\n"
                f"Ends: {end_str}\n"
                f"Duration: {duration_secs // 60} minutes\n"
                f"Participate online at {url}."
            )

            metadata = {
                "title_slug": slug,
                "start_time": start_ts,
                "duration_seconds": duration_secs,
                "start_datetime": start_dt.isoformat(),
                "end_datetime": end_dt.isoformat(),
                "connector_name": "leetcode",
                "source_type": SourceType.API.value,
            }

            raw_items.append(
                RawItem(
                    title=f"LeetCode: {title}",
                    url=url,
                    content=content,
                    source_name=self.name,
                    source_identifier=f"leetcode-{slug}",
                    published_at=start_dt,
                    metadata=metadata,
                )
            )

        logger.info(f"[LeetCodeConnector] Extracted {len(raw_items)} contests")
        return raw_items
