"""
Pydantic Schemas for Opportunity
"""
from datetime import datetime
from typing import List, Optional, Union
from pydantic import BaseModel, ConfigDict, Field
from shared.constants import OpportunityCategory, OpportunityStatus, VerificationStatus
from apps.api.schemas.organization import OrganizationRead
from apps.api.schemas.source import SourceRead
from apps.api.schemas.event import EventBase, EventRead


class OpportunityBase(BaseModel):
    title: str = Field(..., min_length=2, max_length=512)
    canonical_name: Optional[str] = None
    season: Optional[str] = None
    year: Optional[int] = None
    current_state: Optional[str] = None
    organization_id: Optional[str] = None
    source_id: Optional[str] = None
    category: Union[OpportunityCategory, str] = OpportunityCategory.COMPETITIVE_PROGRAMMING
    event_type: str = Field(default="competition", max_length=50)
    status: Union[OpportunityStatus, str] = OpportunityStatus.ACTIVE
    verification_status: Union[VerificationStatus, str] = VerificationStatus.DISCOVERED
    confidence_score: int = Field(default=50, ge=0, le=100)
    official: bool = False
    eligibility: Optional[str] = None
    target_audience: Optional[str] = None
    application_url: Optional[str] = None
    raw_content: Optional[str] = None
    summary: Optional[str] = None


class OpportunityCreate(OpportunityBase):
    slug: Optional[str] = None
    events: Optional[List[EventBase]] = None


class OpportunityUpdate(BaseModel):
    title: Optional[str] = None
    canonical_name: Optional[str] = None
    season: Optional[str] = None
    year: Optional[int] = None
    current_state: Optional[str] = None
    organization_id: Optional[str] = None
    source_id: Optional[str] = None
    category: Optional[OpportunityCategory] = None
    event_type: Optional[str] = None
    status: Optional[OpportunityStatus] = None
    verification_status: Optional[VerificationStatus] = None
    confidence_score: Optional[int] = Field(None, ge=0, le=100)
    official: Optional[bool] = None
    eligibility: Optional[str] = None
    target_audience: Optional[str] = None
    application_url: Optional[str] = None
    summary: Optional[str] = None


class OpportunityAliasRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    alias: str
    source: Optional[str] = None


class OpportunityRead(OpportunityBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    slug: str
    content_hash: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class OpportunityDetailRead(OpportunityRead):
    organization: Optional[OrganizationRead] = None
    source: Optional[SourceRead] = None
    events: List[EventRead] = []
    aliases: List[OpportunityAliasRead] = []

