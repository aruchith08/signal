"""
Pydantic Schemas for Source
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field
from shared.constants import OpportunityCategory, SourceType, TrustLevel


class SourceBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    organization_id: Optional[str] = None
    category: OpportunityCategory = OpportunityCategory.COMPETITIVE_PROGRAMMING
    source_type: SourceType = SourceType.API
    base_url: str = Field(..., max_length=1024)
    api_endpoint: Optional[str] = Field(None, max_length=1024)
    monitor_frequency_minutes: int = Field(default=60, ge=1)
    priority: int = Field(default=1, ge=1, le=10)
    trust_level: TrustLevel = TrustLevel.HIGH
    is_active: bool = True
    notes: Optional[str] = None


class SourceCreate(SourceBase):
    slug: Optional[str] = Field(None, max_length=255)


class SourceUpdate(BaseModel):
    name: Optional[str] = None
    organization_id: Optional[str] = None
    category: Optional[OpportunityCategory] = None
    source_type: Optional[SourceType] = None
    base_url: Optional[str] = None
    api_endpoint: Optional[str] = None
    monitor_frequency_minutes: Optional[int] = None
    priority: Optional[int] = None
    trust_level: Optional[TrustLevel] = None
    is_active: Optional[bool] = None
    notes: Optional[str] = None


class SourceRead(SourceBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    slug: str
    last_polled_at: Optional[datetime] = None
    last_successful_check: Optional[datetime] = None
    failure_count: int = 0
    consecutive_failures: int = 0
    average_response_time: Optional[float] = None
    last_error: Optional[str] = None
    status: str = "healthy"
    polling_policy: Optional[str] = None
    priority_level: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class SourceHealthRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    slug: str
    name: str
    status: str
    failure_count: int
    consecutive_failures: int
    average_response_time_ms: Optional[float] = None
    last_polled_at: Optional[datetime] = None
    last_successful_check: Optional[datetime] = None
    last_error: Optional[str] = None
    polling_policy: Optional[str] = None
    priority_level: Optional[str] = None

