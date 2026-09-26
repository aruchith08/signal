"""
GitHub Tech Blog Live Source Connector
Fetches official engineering announcements, student programs, and product releases from GitHub's RSS feed.
"""
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import html
import logging
import re
from typing import List, Optional
import xml.etree.ElementTree as ET

from connectors.base_connector import BaseConnector, RawItem
from services.ingestion.http_client import ResilientHTTPClient
from shared.constants import OpportunityCategory, SourceType, TrustLevel

logger = logging.getLogger("signal.connectors.github_blog")

GITHUB_BLOG_FEED_URL = "https://github.blog/feed/"


def clean_html(raw_html: str) -> str:
    """Remove HTML tags and unescape HTML entities to produce clean text."""
    if not raw_html:
        return ""
    # Strip HTML tags
    clean = re.sub(r"<[^>]+>", " ", raw_html)
    # Unescape HTML entities
    clean = html.unescape(clean)
    # Collapse multiple whitespaces
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean


class GitHubBlogConnector(BaseConnector):
    """Live connector for GitHub Blog RSS Feed."""

    def __init__(
        self,
        feed_url: str = GITHUB_BLOG_FEED_URL,
        max_items: int = 20,
        is_active: bool = True,
    ):
        super().__init__(
            name="GitHub Blog",
            category=OpportunityCategory.MAJOR_COMPANY_PROGRAM,
            source_type=SourceType.RSS,
            trust_level=TrustLevel.HIGH,
            base_url="https://github.blog",
            is_active=is_active,
        )

        self.feed_url = feed_url
        self.max_items = max_items

    async def health_check(self) -> bool:
        """Verify GitHub Blog RSS feed accessibility."""
        try:
            async with ResilientHTTPClient(timeout=10.0) as client:
                res = await client.get(self.feed_url)
                return res.status_code == 200 and b"<rss" in res.content
        except Exception as exc:
            logger.warning(f"[GitHubBlogConnector] Health check failed: {exc}")
            return False

    async def fetch_raw_items(self) -> List[RawItem]:
        """Fetch and parse GitHub Blog RSS items."""
        async with ResilientHTTPClient(timeout=15.0) as client:
            response = await client.get(self.feed_url)
            xml_bytes = response.content

        try:
            root = ET.fromstring(xml_bytes)
        except ET.ParseError as pe:
            logger.error(f"[GitHubBlogConnector] XML parse error: {pe}")
            raise ValueError(f"Failed to parse GitHub RSS feed: {pe}")

        items = root.findall(".//channel/item")
        if not items:
            items = root.findall(".//item")

        raw_items: List[RawItem] = []
        for item_node in items[: self.max_items]:
            title_node = item_node.find("title")
            title = title_node.text.strip() if title_node is not None and title_node.text else "GitHub Announcement"

            link_node = item_node.find("link")
            link = link_node.text.strip() if link_node is not None and link_node.text else ""

            guid_node = item_node.find("guid")
            guid = guid_node.text.strip() if guid_node is not None and guid_node.text else link

            pubdate_node = item_node.find("pubDate")
            published_at: Optional[datetime] = None
            if pubdate_node is not None and pubdate_node.text:
                try:
                    published_at = parsedate_to_datetime(pubdate_node.text)
                    if published_at.tzinfo is None:
                        published_at = published_at.replace(tzinfo=timezone.utc)
                except Exception:
                    published_at = None

            # Extract content from description and/or content:encoded
            desc_node = item_node.find("description")
            description = clean_html(desc_node.text) if desc_node is not None and desc_node.text else ""

            # Check for content:encoded (namespaced)
            content_encoded = ""
            for child in item_node:
                if child.tag.endswith("encoded") and child.text:
                    content_encoded = clean_html(child.text)
                    break

            full_content = f"{description}\n\n{content_encoded}".strip() if content_encoded else description
            if not full_content:
                full_content = title

            # Extract categories
            categories = [
                c.text.strip()
                for c in item_node.findall("category")
                if c.text and c.text.strip()
            ]

            raw_item = RawItem(
                title=title,
                url=link or guid,
                content=f"GitHub Blog Post: {title}\nCategories: {', '.join(categories)}\n\n{full_content}",
                source_name=self.name,
                source_identifier=guid or link,
                published_at=published_at,
                metadata={
                    "guid": guid,
                    "categories": categories,
                    "feed_url": self.feed_url,
                },
            )
            raw_items.append(raw_item)

        logger.info(f"[GitHubBlogConnector] Fetched {len(raw_items)} items from GitHub Blog feed")
        return raw_items
