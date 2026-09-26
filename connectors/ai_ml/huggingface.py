"""
Hugging Face AI Competitions & Community Challenges Connector
Monitors official Hugging Face open-source model competitions, benchmarks, and sprint hackathons.
"""
from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
from connectors.base_connector import BaseConnector, RawItem
from services.ingestion.http_client import ResilientHTTPClient
from shared.constants import OpportunityCategory, SourceType, TrustLevel
from shared.utils import parse_iso_datetime

logger = logging.getLogger("signal.connectors.huggingface")

HUGGINGFACE_COMPETITIONS_URL = "https://huggingface.co/api/competitions"


class HuggingFaceConnector(BaseConnector):
    """Production connector for Hugging Face community competitions and sprint hackathons."""

    def __init__(
        self,
        api_url: str = HUGGINGFACE_COMPETITIONS_URL,
        is_active: bool = True,
    ):
        super().__init__(
            name="Hugging Face",
            category=OpportunityCategory.AI_ML,
            source_type=SourceType.API,
            trust_level=TrustLevel.HIGH,
            base_url="https://huggingface.co",
            is_active=is_active,
        )
        self.api_url = api_url

    async def health_check(self) -> bool:
        """Verify Hugging Face API reachability."""
        import os
        headers = {"Accept": "application/json", "User-Agent": "SIGNAL-Intelligence/1.0"}
        token = os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACE_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        try:
            async with ResilientHTTPClient(timeout=10.0) as client:
                res = await client.get(
                    self.api_url,
                    headers=headers,
                )
                return res.status_code in (200, 301, 302, 401, 404)
        except Exception as exc:
            if "401" in str(exc) or "403" in str(exc):
                return True
            logger.warning(f"[HuggingFaceConnector] Health check failed: {exc}")
            return False

    async def fetch_raw_items(self) -> List[RawItem]:
        """Fetch active competitions and AI hackathons from Hugging Face."""
        import os
        headers = {"Accept": "application/json", "User-Agent": "SIGNAL-Intelligence/1.0"}
        token = os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACE_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"

        raw_items: List[RawItem] = []

        try:
            async with ResilientHTTPClient(timeout=15.0) as client:
                response = await client.get(
                    self.api_url,
                    headers=headers,
                )
                if response.status_code == 200:
                    data = response.json()
                    competitions = data if isinstance(data, list) else data.get("items", [])
                    for item in competitions:
                        try:
                            comp_id = item.get("id") or item.get("slug") or item.get("name", "")
                            title = item.get("title") or item.get("name") or "Hugging Face Challenge"
                            description = item.get("description") or item.get("task") or ""
                            url = item.get("url") or f"https://huggingface.co/competitions/{comp_id}"
                            deadline_raw = item.get("deadline") or item.get("end_date") or item.get("endDate")
                            deadline_dt = parse_iso_datetime(deadline_raw) if deadline_raw else None

                            prize = item.get("prize") or item.get("reward") or "Community Badges & Compute Grants"

                            raw_items.append(
                                RawItem(
                                    title=title,
                                    url=url,
                                    content=f"{title}\nPlatform: Hugging Face\nReward: {prize}\n\n{description}",
                                    source_name="Hugging Face",
                                    source_identifier=str(comp_id),
                                    published_at=datetime.now(timezone.utc),
                                    metadata={
                                        "organization": "Hugging Face",
                                        "category": OpportunityCategory.AI_ML.value,
                                        "deadline": deadline_dt.isoformat() if deadline_dt else None,
                                        "prize": prize,
                                        "location": "Remote / Online",
                                        "eligibility": "Global AI community, researchers, open source developers",
                                    },
                                )
                            )
                        except Exception as parse_err:
                            logger.warning(f"[HuggingFaceConnector] Skipped malformed item: {parse_err}")
                            continue
        except Exception as exc:
            logger.warning(f"[HuggingFaceConnector] Upstream request failed: {exc}")

        return raw_items
