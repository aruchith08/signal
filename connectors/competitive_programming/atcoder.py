"""
AtCoder Competitive Programming Source Connector
Monitors official AtCoder Beginner Contest (ABC), Regular Contest (ARC), and Grand Contest (AGC).
"""
from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
from connectors.base_connector import BaseConnector, RawItem
from services.ingestion.http_client import ResilientHTTPClient
from shared.constants import OpportunityCategory, SourceType, TrustLevel
from shared.utils import parse_iso_datetime

logger = logging.getLogger("signal.connectors.atcoder")

ATCODER_CONTESTS_API_URL = "https://kenkoooo.com/atcoder/resources/contests.json"


class AtCoderConnector(BaseConnector):
    """Production connector for AtCoder global competitive programming contests."""

    def __init__(
        self,
        api_url: str = ATCODER_CONTESTS_API_URL,
        limit_future: int = 15,
        is_active: bool = True,
    ):
        super().__init__(
            name="AtCoder",
            category=OpportunityCategory.COMPETITIVE_PROGRAMMING,
            source_type=SourceType.API,
            trust_level=TrustLevel.HIGHEST,
            base_url="https://atcoder.jp",
            is_active=is_active,
        )
        self.api_url = api_url
        self.limit_future = limit_future

    async def health_check(self) -> bool:
        """Verify AtCoder contest resource endpoint responsiveness."""
        try:
            async with ResilientHTTPClient(timeout=10.0) as client:
                res = await client.get(
                    self.api_url,
                    headers={"Accept": "application/json", "User-Agent": "SIGNAL-Intelligence/1.0"},
                )
                return res.status_code == 200
        except Exception as exc:
            logger.warning(f"[AtCoderConnector] Health check failed: {exc}")
            return False

    async def fetch_raw_items(self) -> List[RawItem]:
        """Fetch upcoming and active AtCoder contests."""
        raw_items: List[RawItem] = []
        now_epoch = datetime.now(timezone.utc).timestamp()

        try:
            async with ResilientHTTPClient(timeout=15.0) as client:
                response = await client.get(
                    self.api_url,
                    headers={"Accept": "application/json", "User-Agent": "SIGNAL-Intelligence/1.0"},
                )
                if response.status_code == 200:
                    contests = response.json()
                    if isinstance(contests, list):
                        # Filter to upcoming contests or recently started contests
                        upcoming = [
                            c for c in contests
                            if c.get("start_epoch_second", 0) + c.get("duration_second", 0) >= now_epoch - 86400
                        ]
                        # Sort by start epoch ascending
                        upcoming.sort(key=lambda c: c.get("start_epoch_second", 0))

                        for contest in upcoming[: self.limit_future]:
                            try:
                                cid = contest.get("id")
                                title = contest.get("title", f"AtCoder Contest {cid}")
                                start_epoch = contest.get("start_epoch_second")
                                duration = contest.get("duration_second", 0)

                                start_dt = datetime.fromtimestamp(start_epoch, tz=timezone.utc) if start_epoch else None
                                end_dt = datetime.fromtimestamp(start_epoch + duration, tz=timezone.utc) if start_epoch and duration else None

                                url = f"https://atcoder.jp/contests/{cid}"

                                raw_items.append(
                                    RawItem(
                                        title=title,
                                        url=url,
                                        content=f"AtCoder Contest: {title}\nDuration: {duration // 60} minutes\nRated: {contest.get('rate_change', '-')}",
                                        source_name="AtCoder",
                                        source_identifier=str(cid),
                                        published_at=datetime.now(timezone.utc),
                                        metadata={
                                            "organization": "AtCoder",
                                            "category": OpportunityCategory.COMPETITIVE_PROGRAMMING.value,
                                            "start_date": start_dt.isoformat() if start_dt else None,
                                            "deadline": end_dt.isoformat() if end_dt else None,
                                            "duration_seconds": duration,
                                            "location": "Online / Virtual",
                                            "eligibility": "Global competitive programmers and algorithmic developers",
                                        },
                                    )
                                )
                            except Exception as item_err:
                                logger.warning(f"[AtCoderConnector] Error parsing contest item: {item_err}")
                                continue
        except Exception as exc:
            logger.warning(f"[AtCoderConnector] Upstream request failed: {exc}")

        return raw_items
