"""
Google Open Source & GSoC Live Source Connector
Fetches official Google Summer of Code and open source announcements from Google's official feed.
"""
from datetime import datetime, timezone
import html
import logging
import re
from typing import List, Optional
from connectors.base_connector import BaseConnector, RawItem
from services.ingestion.http_client import ResilientHTTPClient
from shared.constants import OpportunityCategory, SourceType, TrustLevel
from shared.utils import parse_iso_datetime


logger = logging.getLogger("signal.connectors.gsoc")

GOOGLE_OPENSOURCE_FEED_URL = "https://opensource.googleblog.com/feeds/posts/default?alt=json"


def strip_html_tags(raw_html: str) -> str:
    """Remove HTML tags and clean up whitespace."""
    if not raw_html:
        return ""
    clean = re.sub(r"<[^>]+>", " ", raw_html)
    clean = html.unescape(clean)
    return re.sub(r"\s+", " ", clean).strip()


class GSoCConnector(BaseConnector):
    """Live connector for Google Open Source and Google Summer of Code announcements."""

    def __init__(
        self,
        feed_url: str = GOOGLE_OPENSOURCE_FEED_URL,
        max_items: int = 25,
        is_active: bool = True,
    ):
        super().__init__(
            name="Google Summer of Code",
            category=OpportunityCategory.OPEN_SOURCE_PROGRAM,
            source_type=SourceType.JSON_FEED,
            trust_level=TrustLevel.HIGHEST,
            base_url="https://opensource.googleblog.com",
            is_active=is_active,
        )
        self.feed_url = feed_url
        self.max_items = max_items

    async def health_check(self) -> bool:
        """Verify Google Open Source feed availability."""
        try:
            async with ResilientHTTPClient(timeout=10.0) as client:
                res = await client.get(self.feed_url)
                if res.status_code != 200:
                    return False
                data = res.json()
                return "feed" in data
        except Exception as exc:
            logger.warning(f"[GSoCConnector] Health check failed: {exc}")
            return False

    async def fetch_raw_items(self) -> List[RawItem]:
        """Fetch latest posts from Google Open Source."""
        async with ResilientHTTPClient(timeout=15.0) as client:
            response = await client.get(self.feed_url)
            payload = response.json()

        entries = payload.get("feed", {}).get("entry", [])
        raw_items: List[RawItem] = []

        for entry in entries[:self.max_items]:
            title_dict = entry.get("title", {})
            title = title_dict.get("$t", "").strip() if isinstance(title_dict, dict) else str(title_dict)

            id_dict = entry.get("id", {})
            entry_id = id_dict.get("$t", "") if isinstance(id_dict, dict) else str(id_dict)

            if not title:
                continue

            # Find canonical link
            links = entry.get("link", [])
            post_url = ""
            for l in links:
                if l.get("rel") == "alternate":
                    post_url = l.get("href", "")
                    break
            if not post_url and links:
                post_url = links[0].get("href", "")

            # Parse content
            content_dict = entry.get("content", {}) or entry.get("summary", {})
            raw_text = content_dict.get("$t", "") if isinstance(content_dict, dict) else ""
            clean_text = strip_html_tags(raw_text)

            # Published timestamp
            pub_dict = entry.get("published", {})
            pub_str = pub_dict.get("$t", "") if isinstance(pub_dict, dict) else ""
            pub_date = parse_iso_datetime(pub_str) if pub_str else None
            if not pub_date:
                pub_date = datetime.now(timezone.utc)


            metadata = {
                "entry_id": entry_id,
                "author": entry.get("author", [{}])[0].get("name", {}).get("$t", "Google Open Source"),
                "connector_name": "gsoc",
                "source_type": SourceType.JSON_FEED.value,
            }

            raw_items.append(
                RawItem(
                    title=f"Google Open Source: {title}",
                    url=post_url,
                    content=clean_text[:4000] if clean_text else title,
                    source_name=self.name,
                    source_identifier=entry_id.split(".")[-1] if "." in entry_id else entry_id or post_url,
                    published_at=pub_date,
                    metadata=metadata,
                )
            )

        logger.info(f"[GSoCConnector] Extracted {len(raw_items)} announcements")
        return raw_items
