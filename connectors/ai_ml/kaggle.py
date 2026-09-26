"""
Kaggle AI/ML Competitions Live Source Connector
Monitors official Kaggle machine learning competitions, data challenges, and benchmarks.
"""
from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
from connectors.base_connector import BaseConnector, RawItem
from services.ingestion.http_client import ResilientHTTPClient
from shared.constants import OpportunityCategory, SourceType, TrustLevel
from shared.utils import parse_iso_datetime

logger = logging.getLogger("signal.connectors.kaggle")

KAGGLE_PUBLIC_COMPETITIONS_URL = "https://www.kaggle.com/api/v1/competitions/list"


class KaggleConnector(BaseConnector):
    """Production connector for Kaggle Machine Learning and AI competitions."""

    def __init__(
        self,
        api_url: str = KAGGLE_PUBLIC_COMPETITIONS_URL,
        page: int = 1,
        page_size: int = 50,
        is_active: bool = True,
    ):
        super().__init__(
            name="Kaggle",
            category=OpportunityCategory.AI_ML,
            source_type=SourceType.API,
            trust_level=TrustLevel.HIGH,
            base_url="https://www.kaggle.com",
            is_active=is_active,
        )
        self.api_url = api_url
        self.page = page
        self.page_size = page_size

    async def health_check(self) -> bool:
        """Verify Kaggle competition API accessibility."""
        import base64
        import os
        headers = {"Accept": "application/json", "User-Agent": "SIGNAL-Intelligence/1.0"}
        if os.getenv("KAGGLE_USERNAME") and os.getenv("KAGGLE_KEY"):
            creds = f"{os.getenv('KAGGLE_USERNAME')}:{os.getenv('KAGGLE_KEY')}".encode()
            headers["Authorization"] = f"Basic {base64.b64encode(creds).decode()}"
        try:
            async with ResilientHTTPClient(timeout=10.0) as client:
                res = await client.get(
                    self.api_url,
                    params={"page": 1, "pageSize": 1},
                    headers=headers,
                )
                return res.status_code in (200, 401, 403)
        except Exception as exc:
            if "401" in str(exc) or "403" in str(exc):
                return True
            logger.warning(f"[KaggleConnector] Health check failed: {exc}")
            return False

    async def fetch_raw_items(self) -> List[RawItem]:
        """Fetch active machine learning competitions from Kaggle."""
        import base64
        import os
        headers = {"Accept": "application/json", "User-Agent": "SIGNAL-Intelligence/1.0"}
        if os.getenv("KAGGLE_USERNAME") and os.getenv("KAGGLE_KEY"):
            creds = f"{os.getenv('KAGGLE_USERNAME')}:{os.getenv('KAGGLE_KEY')}".encode()
            headers["Authorization"] = f"Basic {base64.b64encode(creds).decode()}"

        raw_items: List[RawItem] = []

        try:
            async with ResilientHTTPClient(timeout=15.0) as client:
                response = await client.get(
                    self.api_url,
                    params={"page": self.page, "pageSize": self.page_size},
                    headers=headers,
                )
                if response.status_code == 200:
                    data = response.json()
                    competitions = data if isinstance(data, list) else data.get("competitions", [])
                    for item in competitions:
                        try:
                            ref = item.get("ref") or item.get("id") or item.get("url", "")
                            title = item.get("title") or item.get("name") or "Kaggle Competition"
                            description = item.get("description") or item.get("summary") or ""
                            url = f"https://www.kaggle.com/c/{ref}" if ref and not str(ref).startswith("http") else str(ref)
                            deadline_raw = item.get("deadline") or item.get("deadlineDate")
                            deadline_dt = parse_iso_datetime(deadline_raw) if deadline_raw else None

                            prize = item.get("reward") or item.get("prize") or "Prizes / Knowledge"
                            category_type = item.get("category", "Featured")

                            raw_items.append(
                                RawItem(
                                    title=title,
                                    url=url,
                                    content=f"{title}\nCategory: {category_type}\nPrize: {prize}\n\n{description}",
                                    source_name="Kaggle",
                                    source_identifier=str(ref),
                                    published_at=datetime.now(timezone.utc),
                                    metadata={
                                        "organization": "Kaggle",
                                        "category": OpportunityCategory.AI_ML.value,
                                        "deadline": deadline_dt.isoformat() if deadline_dt else None,
                                        "prize": prize,
                                        "location": "Remote / Online",
                                        "eligibility": "Global AI/ML developers, students, researchers",
                                        "competition_category": category_type,
                                    },
                                )
                            )
                        except Exception as parse_err:
                            logger.warning(f"[KaggleConnector] Skipped malformed item: {parse_err}")
                            continue
        except Exception as exc:
            logger.warning(f"[KaggleConnector] Upstream request failed: {exc}")

        return raw_items
