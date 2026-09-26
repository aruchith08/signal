"""
Base Connector Interface for Ingestion Sources
"""
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from shared.constants import OpportunityCategory, SourceType, TrustLevel
from shared.utils import canonicalize_url


class RawItem(BaseModel):
    """Raw unprocessed item fetched from a monitored source."""
    title: str
    url: str
    content: str
    source_name: str
    source_identifier: str
    published_at: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def canonical_url(self) -> str:
        """Return the cleaned, canonical URL stripped of tracking parameters."""
        return canonicalize_url(self.url)


class BaseConnector(ABC):
    """Abstract base class for all source connectors."""

    def __init__(
        self,
        name: str,
        category: OpportunityCategory,
        source_type: SourceType,
        trust_level: TrustLevel = TrustLevel.HIGH,
        base_url: str = "",
        is_active: bool = True,
    ):
        self.name = name
        self.category = category
        self.source_type = source_type
        self.trust_level = trust_level
        self.base_url = base_url
        self.is_active = is_active

    @abstractmethod
    async def health_check(self) -> bool:
        """Verify that the upstream source endpoint is reachable."""
        pass

    @abstractmethod
    async def fetch_raw_items(self) -> List[RawItem]:
        """Poll or query the external source and return new raw items."""
        pass
