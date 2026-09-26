"""
Pydantic Schemas for User Opportunity Interactions (Saved & Followed)
"""
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict


class UserOpportunityInteractionBase(BaseModel):
    is_saved: bool = False
    is_followed: bool = False
    notes: Optional[str] = None


class UserOpportunityInteractionRead(UserOpportunityInteractionBase):
    id: str
    user_id: str
    opportunity_id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserInteractionsOverviewResponse(BaseModel):
    saved_opportunity_ids: List[str]
    followed_opportunity_ids: List[str]


class UserInteractionStatusResponse(BaseModel):
    opportunity_id: str
    is_saved: bool
    is_followed: bool
    notes: Optional[str] = None
