"""
Pydantic Schemas for Dashboard Aggregation Overview
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel
from apps.api.schemas.opportunity import OpportunityRead
from apps.api.schemas.event import EventRead


class TopPriorityItem(BaseModel):
    opportunity: OpportunityRead
    event: Optional[EventRead] = None
    urgency_label: str
    relevance_score: Optional[int] = None
    why_it_matters: Optional[str] = None


class PersonalizedOpportunityItem(BaseModel):
    opportunity: OpportunityRead
    relevance_score: int
    eligibility: str
    match_factors: List[str]
    nearest_deadline: Optional[datetime] = None
    urgency_label: Optional[str] = None


class DeadlineApproachingItem(BaseModel):
    opportunity_id: str
    opportunity_title: str
    organization_name: Optional[str] = None
    category: str
    deadline_date: datetime
    urgency_label: str
    is_critical: bool


class DashboardOverviewResponse(BaseModel):
    top_priority: Optional[TopPriorityItem] = None
    for_you: List[PersonalizedOpportunityItem] = []
    recent_announcements: List[OpportunityRead] = []
    deadlines_approaching: List[DeadlineApproachingItem] = []
    recent_updates: List[Dict[str, Any]] = []
    stats: Dict[str, Any] = {}
