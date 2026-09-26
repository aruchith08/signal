"""
HackerRank Live Source Connector
Fetches official upcoming coding competitions from HackerRank's public REST API.
"""
from datetime import datetime, timezone
import logging
from typing import List, Optional
from connectors.base_connector import BaseConnector, RawItem
from services.ingestion.http_client import ResilientHTTPClient
from shared.constants import OpportunityCategory, SourceType, TrustLevel

logger = logging.getLogger("signal.connectors.hackerrank")

HACKERRANK_API_URL = "https://www.hackerrank.com/rest/contests/upcoming"


class HackerRankConnector(BaseConnector):
    """Live connector for HackerRank competitive programming contests."""

    def __init__(
        self,
        api_url: str = HACKERRANK_API_URL,
        is_active: bool = True,
    ):
        super().__init__(
            name="HackerRank",
            category=OpportunityCategory.COMPETITIVE_PROGRAMMING,
            source_type=SourceType.API,
            trust_level=TrustLevel.HIGH,
            base_url="https://www.hackerrank.com",
            is_active=is_active,
        )
        self.api_url = api_url

    async def health_check(self) -> bool:
        """Verify HackerRank API responsiveness."""
        try:
            async with ResilientHTTPClient(timeout=10.0) as client:
                res = await client.get(self.api_url)
                if res.status_code != 200:
                    return False
                data = res.json()
                return "models" in data
        except Exception as exc:
            logger.warning(f"[HackerRankConnector] Health check failed: {exc}")
            return False

    async def fetch_raw_items(self) -> List[RawItem]:
        """Fetch upcoming and ongoing competitions from HackerRank."""
        async with ResilientHTTPClient(timeout=15.0) as client:
            response = await client.get(self.api_url)
            payload = response.json()

        models = payload.get("models", []) if isinstance(payload, dict) else []
        raw_items: List[RawItem] = []

        for m in models:
            slug = m.get("slug", "").strip()
            name = m.get("name", "").strip()
            if not slug or not name:
                continue

            epoch_start = m.get("epoch_starttime")
            epoch_end = m.get("epoch_endtime")

            start_dt = None
            if epoch_start:
                try:
                    start_dt = datetime.fromtimestamp(epoch_start, tz=timezone.utc)
                except Exception:
                    start_dt = datetime.now(timezone.utc)

            end_dt = None
            if epoch_end:
                try:
                    end_dt = datetime.fromtimestamp(epoch_end, tz=timezone.utc)
                except Exception:
                    pass

            start_str = start_dt.strftime("%d %B %Y %H:%M UTC") if start_dt else "TBA"
            end_str = end_dt.strftime("%d %B %Y %H:%M UTC") if end_dt else "TBA"

            url = f"https://www.hackerrank.com/contests/{slug}"
            description = m.get("description") or f"HackerRank coding contest: {name}"
            content = (
                f"HackerRank Contest: {name}\n"
                f"{description}\n"
                f"Starts: {start_str}\n"
                f"Ends: {end_str}\n"
                f"Compete online at {url}."
            )

            metadata = {
                "slug": slug,
                "contest_name": name,
                "epoch_starttime": epoch_start,
                "epoch_endtime": epoch_end,
                "start_datetime": start_dt.isoformat() if start_dt else None,
                "end_datetime": end_dt.isoformat() if end_dt else None,
                "connector_name": "hackerrank",
                "source_type": SourceType.API.value,
            }

            raw_items.append(
                RawItem(
                    title=f"HackerRank: {name}",
                    url=url,
                    content=content,
                    source_name=self.name,
                    source_identifier=f"hackerrank-{slug}",
                    published_at=start_dt,
                    metadata=metadata,
                )
            )

        logger.info(f"[HackerRankConnector] Extracted {len(raw_items)} contests")
        return raw_items
