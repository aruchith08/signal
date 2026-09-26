"""
Pydantic Schemas for SourceSnapshot
"""
from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict, Field


class SourceSnapshotBase(BaseModel):
    source_id: str
    snapshot_hash: str
    content_hash: str
    normalized_content: Optional[str] = None
    items_count: int = 0
    fetched_at: datetime
    status: str = "success"
    change_type: Optional[str] = "no_change"
    metadata_json: Optional[Dict[str, Any]] = None


class SourceSnapshotCreate(SourceSnapshotBase):
    raw_content: Optional[str] = None


class SourceSnapshotRead(SourceSnapshotBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
    updated_at: datetime
