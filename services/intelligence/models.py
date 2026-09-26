"""
Data transfer objects for AI Gateway results
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from shared.constants import OpportunityCategory, OpportunityStatus


class ClassificationResult(BaseModel):
    is_opportunity: bool = Field(..., description="Whether content represents an opportunity")
    category: Optional[OpportunityCategory] = Field(None, description="Inferred category")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score from 0.0 to 1.0")
    reasoning: str = Field(..., description="Brief explanation of the classification")
    provider: str = Field(..., description="Provider that produced this classification")


class ExtractionResult(BaseModel):
    title: str = Field(..., description="Title of the opportunity")
    organization: Optional[str] = Field(None, description="Host organization")
    category: OpportunityCategory = Field(..., description="Category")
    event_type: str = Field(default="competition", description="Event type")
    status: OpportunityStatus = Field(default=OpportunityStatus.ACTIVE)
    eligibility: Optional[str] = Field(None, description="Eligibility criteria")
    target_audience: Optional[str] = Field(None, description="e.g. B.Tech students, developers")
    application_url: Optional[str] = Field(None, description="Application or registration URL")
    events: List[Dict[str, Any]] = Field(default_factory=list, description="Extracted dates and events")
    summary: str = Field(..., description="Clear concise summary")
    confidence: float = Field(..., ge=0.0, le=1.0)
    provider: str = Field(..., description="Provider that performed extraction")


class SummarizationResult(BaseModel):
    summary: str = Field(..., description="Executive summary")
    key_highlights: List[str] = Field(default_factory=list, description="Key bullet points")
    action_items: List[str] = Field(default_factory=list, description="Immediate next steps / deadlines")
    provider: str = Field(..., description="Provider that produced the summary")
