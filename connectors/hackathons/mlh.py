"""
Major League Hacking (MLH) Live Source Connector
Fetches official global student hackathons from MLH's official season schedule.
"""
from datetime import datetime, timezone
import html
import logging
import re
from typing import List, Optional
from connectors.base_connector import BaseConnector, RawItem
from services.ingestion.http_client import ResilientHTTPClient
from shared.constants import OpportunityCategory, SourceType, TrustLevel

logger = logging.getLogger("signal.connectors.mlh")

MLH_SEASON_URL = "https://mlh.io/seasons/2026/events"


def clean_text(raw: str) -> str:
    """Remove HTML tags, comments, and collapse whitespace."""
    if not raw:
        return ""
    clean = re.sub(r"<[^>]+>", " ", raw)
    clean = html.unescape(clean)
    return re.sub(r"\s+", " ", clean).strip()


class MLHConnector(BaseConnector):
    """Live connector for Major League Hacking global hackathons."""

    def __init__(
        self,
        season_url: str = MLH_SEASON_URL,
        max_items: int = 30,
        is_active: bool = True,
    ):
        super().__init__(
            name="Major League Hacking",
            category=OpportunityCategory.HACKATHON,
            source_type=SourceType.OFFICIAL_WEBSITE,
            trust_level=TrustLevel.HIGH,
            base_url="https://mlh.io",
            is_active=is_active,
        )
        self.season_url = season_url
        self.max_items = max_items

    async def health_check(self) -> bool:
        """Verify MLH season portal availability."""
        try:
            async with ResilientHTTPClient(timeout=12.0) as client:
                res = await client.get(self.season_url)
                return res.status_code == 200 and ("mlh" in res.text.lower() or "hackathon" in res.text.lower())
        except Exception as exc:
            logger.warning(f"[MLHConnector] Health check failed: {exc}")
            return False

    async def fetch_raw_items(self) -> List[RawItem]:
        """Fetch and parse hackathons from the MLH schedule."""
        async with ResilientHTTPClient(timeout=15.0) as client:
            res = await client.get(self.season_url)
            page_html = res.text

        # Extract event blocks or cards
        # Matches event names and urls
        event_pattern = re.compile(
            r'<div[^>]*class=["\'][^"\']*event-wrapper[^"\']*["\'][^>]*>(.*?)</div>\s*</div>',
            re.DOTALL | re.IGNORECASE,
        )
        blocks = event_pattern.findall(page_html)

        raw_items: List[RawItem] = []
        seen_titles = set()

        if not blocks:
            # Fallback anchor search if wrapper class varies
            card_pattern = re.compile(
                r'<a[^>]+href=["\'](https?://[^"\']+)["\'][^>]*title=["\']([^"\']+)["\'][^>]*>',
                re.IGNORECASE,
            )
            for link, title in card_pattern.findall(page_html):
                clean_title = clean_text(title)
                if not clean_title or clean_title in seen_titles:
                    continue
                seen_titles.add(clean_title)
                slug = re.sub(r"[^a-zA-Z0-9]+", "-", clean_title).strip("-").lower()
                raw_items.append(
                    RawItem(
                        title=f"MLH: {clean_title}",
                        url=link,
                        content=f"Major League Hacking Season Event: {clean_title}\nRegister and participate at {link}.",
                        source_name=self.name,
                        source_identifier=f"mlh-{slug}",
                        published_at=datetime.now(timezone.utc),
                        metadata={"connector_name": "mlh", "source_type": SourceType.OFFICIAL_WEBSITE.value},
                    )
                )
                if len(raw_items) >= self.max_items:
                    break
            return raw_items

        for block in blocks:
            # Extract title
            title_match = re.search(r'<h3[^>]*>(.*?)</h3>', block, re.DOTALL | re.IGNORECASE)
            title = clean_text(title_match.group(1)) if title_match else ""

            # Extract link
            link_match = re.search(r'<a[^>]+href=["\']([^"\']+)["\']', block, re.IGNORECASE)
            url = link_match.group(1) if link_match else ""

            # Extract date
            date_match = re.search(r'<p[^>]*class=["\'][^"\']*event-date[^"\']*["\'][^>]*>(.*?)</p>', block, re.DOTALL | re.IGNORECASE)
            date_str = clean_text(date_match.group(1)) if date_match else ""

            # Extract location
            loc_match = re.search(r'<div[^>]*class=["\'][^"\']*event-location[^"\']*["\'][^>]*>(.*?)</div>', block, re.DOTALL | re.IGNORECASE)
            loc_str = clean_text(loc_match.group(1)) if loc_match else ""

            if not title or title in seen_titles:
                continue
            seen_titles.add(title)

            if not url or url.startswith("/"):
                url = f"https://mlh.io{url}" if url.startswith("/") else f"https://mlh.io/events/{title.lower().replace(' ', '-')}"

            slug = re.sub(r"[^a-zA-Z0-9]+", "-", title).strip("-").lower()
            content = (
                f"MLH Hackathon: {title}\n"
                f"Date: {date_str or 'See event page'}\n"
                f"Location: {loc_str or 'Online / Global'}\n"
                f"Official registration and details: {url}"
            )

            metadata = {
                "event_title": title,
                "event_date": date_str,
                "event_location": loc_str,
                "connector_name": "mlh",
                "source_type": SourceType.OFFICIAL_WEBSITE.value,
            }

            raw_items.append(
                RawItem(
                    title=f"MLH: {title}",
                    url=url,
                    content=content,
                    source_name=self.name,
                    source_identifier=f"mlh-{slug}",
                    published_at=datetime.now(timezone.utc),
                    metadata=metadata,
                )
            )

            if len(raw_items) >= self.max_items:
                break

        logger.info(f"[MLHConnector] Extracted {len(raw_items)} hackathons")
        return raw_items
