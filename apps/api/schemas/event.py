"""
Pydantic Schemas for OpportunityEvent
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field
from shared.constants import EventType


class EventBase(BaseModel):
    event_type: EventType = EventType.ANNOUNCEMENT
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    event_date: Optional[datetime] = None
    deadline_date: Optional[datetime] = None
    is_critical: bool = False
    source_discovery_id: Optional[str] = None
    source_url: Optional[str] = None


class EventCreate(EventBase):
    opportunity_id: str


class EventUpdate(BaseModel):
    event_type: Optional[EventType] = None
    title: Optional[str] = None
    description: Optional[str] = None
    event_date: Optional[datetime] = None
    deadline_date: Optional[datetime] = None
    is_critical: Optional[bool] = None
    source_discovery_id: Optional[str] = None
    source_url: Optional[str] = None


class EventRead(EventBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    opportunity_id: str
    created_at: datetime
    updated_at: datetime

