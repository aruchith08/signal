"""
CodeChef Live Source Connector
Fetches official competitive programming challenges from CodeChef's public REST API.
"""
from datetime import datetime, timezone
import logging
from typing import List, Optional
from connectors.base_connector import BaseConnector, RawItem
from services.ingestion.http_client import ResilientHTTPClient
from shared.constants import OpportunityCategory, SourceType, TrustLevel
from shared.utils import parse_iso_datetime


logger = logging.getLogger("signal.connectors.codechef")

CODECHEF_API_URL = "https://www.codechef.com/api/list/contests/all"


class CodeChefConnector(BaseConnector):
    """Live connector for CodeChef contests and challenges."""

    def __init__(
        self,
        api_url: str = CODECHEF_API_URL,
        is_active: bool = True,
    ):
        super().__init__(
            name="CodeChef",
            category=OpportunityCategory.COMPETITIVE_PROGRAMMING,
            source_type=SourceType.API,
            trust_level=TrustLevel.HIGH,
            base_url="https://www.codechef.com",
            is_active=is_active,
        )
        self.api_url = api_url

    async def health_check(self) -> bool:
        """Verify CodeChef API responsiveness."""
        try:
            async with ResilientHTTPClient(timeout=10.0) as client:
                res = await client.get(self.api_url)
                if res.status_code != 200:
                    return False
                data = res.json()
                return "future_contests" in data or "present_contests" in data
        except Exception as exc:
            logger.warning(f"[CodeChefConnector] Health check failed: {exc}")
            return False

    async def fetch_raw_items(self) -> List[RawItem]:
        """Fetch present and future contests from CodeChef."""
        async with ResilientHTTPClient(timeout=15.0) as client:
            response = await client.get(self.api_url)
            payload = response.json()

        contests = []
        if isinstance(payload, dict):
            # Include present and future contests
            contests.extend(payload.get("present_contests", []))
            contests.extend(payload.get("future_contests", []))

        raw_items: List[RawItem] = []
        for c in contests:
            code = c.get("contest_code", "")
            name = c.get("contest_name", "").strip()
            if not code or not name:
                continue

            start_str = c.get("contest_start_date_iso") or c.get("contest_start_date")
            end_str = c.get("contest_end_date_iso") or c.get("contest_end_date")

            pub_date = parse_iso_datetime(start_str) if start_str else None
            if not pub_date:
                pub_date = datetime.now(timezone.utc)


            url = f"https://www.codechef.com/{code}"
            content = (
                f"CodeChef Challenge: {name} (Code: {code})\n"
                f"Starts: {start_str}\n"
                f"Ends: {end_str}\n"
                f"Registration and details available on CodeChef."
            )

            metadata = {
                "contest_code": code,
                "contest_name": name,
                "start_date": start_str,
                "end_date": end_str,
                "connector_name": "codechef",
                "source_type": SourceType.API.value,
            }

            raw_items.append(
                RawItem(
                    title=f"CodeChef: {name}",
                    url=url,
                    content=content,
                    source_name=self.name,
                    source_identifier=f"codechef-{code}",
                    published_at=pub_date,
                    metadata=metadata,
                )
            )

        logger.info(f"[CodeChefConnector] Extracted {len(raw_items)} active/future contests")
        return raw_items
