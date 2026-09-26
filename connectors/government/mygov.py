"""
MyGov Innovate Live Source Connector
Fetches national hackathons, grand challenges, and innovation competitions from the official Indian Government MyGov portal.
"""
from datetime import datetime, timezone
import html
import logging
import re
from typing import List, Optional
from connectors.base_connector import BaseConnector, RawItem
from services.ingestion.http_client import ResilientHTTPClient
from shared.constants import OpportunityCategory, SourceType, TrustLevel

logger = logging.getLogger("signal.connectors.mygov")

MYGOV_INNOVATE_URL = "https://innovateindia.mygov.in/"


def clean_html(text: str) -> str:
    """Remove HTML tags and extra whitespace."""
    if not text:
        return ""
    clean = re.sub(r"<[^>]+>", " ", text)
    clean = html.unescape(clean)
    return re.sub(r"\s+", " ", clean).strip()


class MyGovConnector(BaseConnector):
    """Live connector for MyGov Innovate challenges and hackathons."""

    def __init__(
        self,
        portal_url: str = MYGOV_INNOVATE_URL,
        max_items: int = 25,
        is_active: bool = True,
    ):
        super().__init__(
            name="MyGov Innovate",
            category=OpportunityCategory.GOVERNMENT,
            source_type=SourceType.OFFICIAL_WEBSITE,
            trust_level=TrustLevel.HIGHEST,
            base_url="https://innovateindia.mygov.in",
            is_active=is_active,
        )
        self.portal_url = portal_url
        self.max_items = max_items

    async def health_check(self) -> bool:
        """Verify MyGov Innovate portal responsiveness."""
        try:
            async with ResilientHTTPClient(timeout=12.0) as client:
                res = await client.get(self.portal_url)
                return res.status_code == 200 and ("innovate" in res.text.lower() or "mygov" in res.text.lower())
        except Exception as exc:
            logger.warning(f"[MyGovConnector] Health check failed: {exc}")
            return False

    async def fetch_raw_items(self) -> List[RawItem]:
        """Parse current initiatives, challenges, and hackathons from MyGov Innovate."""
        async with ResilientHTTPClient(timeout=15.0) as client:
            res = await client.get(self.portal_url)
            page_html = res.text

        # Extract initiative/challenge card blocks or anchors
        # Pattern matches links with headings or descriptive text
        pattern = re.compile(
            r'<a[^>]+href=["\'](https://innovateindia\.mygov\.in/[^"\'#]+)["\'][^>]*>(.*?)</a>',
            re.DOTALL | re.IGNORECASE,
        )

        matches = pattern.findall(page_html)
        raw_items: List[RawItem] = []
        seen_urls = set()

        for link, inner_content in matches:
            clean_title = clean_html(inner_content)
            # Filter navigation elements, short links, or image tags without text
            if len(clean_title) < 8 or len(clean_title) > 200:
                continue
            if link in seen_urls:
                continue
            seen_urls.add(link)

            # Skip common non-opportunity nav links
            lower_title = clean_title.lower()
            if any(skip in lower_title for skip in ["home", "about us", "terms", "privacy", "contact", "dashboard"]):
                continue

            slug = link.rstrip("/").split("/")[-1]
            content = (
                f"National Innovation Challenge: {clean_title}\n"
                f"Official Government Initiative hosted on MyGov Innovate India.\n"
                f"Apply and view guidelines at: {link}"
            )

            metadata = {
                "portal_url": link,
                "slug": slug,
                "connector_name": "mygov",
                "source_type": SourceType.OFFICIAL_WEBSITE.value,
            }

            raw_items.append(
                RawItem(
                    title=f"MyGov: {clean_title}",
                    url=link,
                    content=content,
                    source_name=self.name,
                    source_identifier=f"mygov-{slug}",
                    published_at=datetime.now(timezone.utc),
                    metadata=metadata,
                )
            )

            if len(raw_items) >= self.max_items:
                break

        logger.info(f"[MyGovConnector] Extracted {len(raw_items)} challenges and initiatives")
        return raw_items
