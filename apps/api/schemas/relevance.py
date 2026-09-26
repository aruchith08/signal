"""
Pydantic Schemas for Relevance Results and Notification Decisions
"""
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class RelevanceResultRead(BaseModel):
    score: int = Field(ge=0, le=100)
    confidence: float = Field(ge=0.0, le=1.0)
    eligibility_status: str
    reasons: List[str] = []
    matched_interests: List[str] = []
    matched_skills: List[str] = []
    matched_programs: List[str] = []
    component_scores: Dict[str, float] = {}


class NotificationDecisionRead(BaseModel):
    should_notify: bool
    delivery_mode: str
    priority: str
    reason: str
    relevance_result: Optional[RelevanceResultRead] = None
    scheduled_for: Optional[str] = None
