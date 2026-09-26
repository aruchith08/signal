"""
Pydantic Schemas for RawDiscovery
"""
from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict
from shared.constants import DiscoveryStatus


class RawDiscoveryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    source_id: Optional[str] = None
    external_id: Optional[str] = None
    original_url: str
    canonical_url: str
    raw_title: str
    raw_content: str
    published_at: Optional[datetime] = None
    fetched_at: datetime
    content_hash: str
    status: DiscoveryStatus
    content_classification: Optional[str] = None
    matched_by: Optional[str] = None
    processing_reason: Optional[str] = None
    connector_metadata: Optional[Dict[str, Any]] = None
    opportunity_id: Optional[str] = None
    created_event_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime


DiscoveryRead = RawDiscoveryRead

