"""
Smart India Hackathon (SIH) Live Source Connector
Fetches official problem statements and hackathon challenges directly from the SIH national portal.
"""
import html
import logging
import re
from typing import Dict, List, Optional
from connectors.base_connector import BaseConnector, RawItem
from services.ingestion.http_client import ResilientHTTPClient
from shared.constants import OpportunityCategory, SourceType, TrustLevel

logger = logging.getLogger("signal.connectors.sih")

SIH_PS_URL = "https://sih.gov.in/sih2026PS"


def clean_text(raw: str) -> str:
    """Strip HTML tags, comments, and normalize spaces."""
    if not raw:
        return ""
    # Remove HTML comments
    clean = re.sub(r"<!--[\s\S]*?-->", "", raw)
    # Remove HTML tags
    clean = re.sub(r"<[^>]+>", " ", clean)
    # Unescape HTML entities
    clean = html.unescape(clean)
    # Collapse whitespace
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean


class SIHConnector(BaseConnector):
    """Live connector for Smart India Hackathon problem statements and challenges."""

    def __init__(
        self,
        portal_url: str = SIH_PS_URL,
        max_items: int = 50,
        is_active: bool = True,
    ):
        super().__init__(
            name="Smart India Hackathon",
            category=OpportunityCategory.HACKATHON,
            source_type=SourceType.OFFICIAL_WEBSITE,
            trust_level=TrustLevel.HIGHEST,
            base_url="https://sih.gov.in",
            is_active=is_active,
        )

        self.portal_url = portal_url
        self.max_items = max_items

    async def health_check(self) -> bool:
        """Verify SIH portal responsiveness."""
        try:
            async with ResilientHTTPClient(timeout=15.0) as client:
                res = await client.get(self.portal_url)
                return res.status_code == 200 and ("Smart India Hackathon" in res.text or "sih" in res.text.lower())
        except Exception as exc:
            logger.warning(f"[SIHConnector] Health check failed: {exc}")
            return False

    async def fetch_raw_items(self) -> List[RawItem]:
        """Fetch and parse live problem statements from SIH."""
        async with ResilientHTTPClient(timeout=25.0) as client:
            response = await client.get(self.portal_url)
            html_text = response.text

        # Find all modal sections that contain problem details
        # Pattern matches: id="ViewProblemStatement(\d+)" ... </table>
        modal_pattern = re.compile(
            r'id=[\'"]ViewProblemStatement(\d+)[\'"][\s\S]*?<table[\s\S]*?</table>',
            re.IGNORECASE,
        )
        modals = modal_pattern.findall(html_text)

        raw_items: List[RawItem] = []

        # Find full modal blocks
        for match in re.finditer(r'id=[\'"]ViewProblemStatement(\d+)[\'"][\s\S]*?<table[\s\S]*?</table>', html_text):
            if len(raw_items) >= self.max_items:
                break

            ps_id = match.group(1)
            table_html = match.group(0)

            # Parse key-value pairs from table
            row_matches = re.findall(r'<th[^>]*>([\s\S]*?)</th>\s*<td[^>]*>([\s\S]*?)</td>', table_html)
            data: Dict[str, str] = {}
            for h, d in row_matches:
                key = clean_text(h).strip().lower()
                val = clean_text(d).strip()
                data[key] = val

            title = data.get("problem statement title") or f"SIH Problem Statement #{ps_id}"
            org = data.get("organization") or "Ministry / Organization (SIH)"
            desc = data.get("description") or title
            category_type = data.get("category") or "Software"
            theme = data.get("theme") or "General"
            dept = data.get("department") or ""

            url = f"{self.portal_url}?psid={ps_id}"

            content = (

                f"Smart India Hackathon Problem Statement #{ps_id}: {title}\n"
                f"Organization: {org}\n"
                f"Department: {dept}\n"
                f"Category: {category_type}\n"
                f"Theme: {theme}\n"
                f"Portal Link: {url}\n\n"
                f"Description:\n{desc}\n\n"
                f"Opportunity Details:\n"
                f"This official problem statement is part of Smart India Hackathon (SIH), "
                f"India's premier nationwide hackathon initiative for college students and innovators to build technology solutions for government and industry."
            )

            raw_item = RawItem(
                title=f"SIH: {title}",
                url=url,
                content=content,
                source_name=self.name,
                source_identifier=str(ps_id),
                metadata={
                    "ps_id": ps_id,
                    "organization": org,
                    "department": dept,
                    "category": category_type,
                    "theme": theme,
                    "portal_url": self.portal_url,
                },
            )
            raw_items.append(raw_item)

        logger.info(f"[SIHConnector] Successfully extracted {len(raw_items)} problem statements from SIH portal")
        return raw_items
