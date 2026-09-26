"""
Pydantic v2 Schemas for Phase 3 Verification, Sources, Conflicts, and Review Queue
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class OpportunitySourceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    opportunity_id: str
    source_id: Optional[str] = None
    raw_discovery_id: Optional[str] = None
    source_url: str
    canonical_url: str
    source_title: Optional[str] = None
    trust_score: float
    is_primary_source: bool
    is_official_source: bool
    contributed_fields: Optional[str] = None
    created_at: datetime


class VerifiedFieldResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    opportunity_id: str
    field_name: str
    value: Optional[str] = None
    confidence: float
    source_count: int
    official_confirmation: bool
    verification_status: str
    updated_at: datetime


class VerificationConflictResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    opportunity_id: str
    field_name: str
    conflicting_values: Optional[str] = None
    source_details: Optional[str] = None
    status: str
    resolution_notes: Optional[str] = None
    created_at: datetime


class SemanticCandidateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    opportunity_a_id: str
    opportunity_b_id: str
    similarity_score: float
    deterministic_score: float
    ai_score: Optional[float] = None
    final_score: float
    status: str
    decision_reason: Optional[str] = None
    created_at: datetime
    resolved_at: Optional[datetime] = None


class VerificationReviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    entity_type: str
    entity_id: str
    candidate_id: Optional[str] = None
    conflict_id: Optional[str] = None
    reason: str
    priority: str
    status: str
    review_notes: Optional[str] = None
    resolution_action: Optional[str] = None
    created_at: datetime
    resolved_at: Optional[datetime] = None


class ReviewActionRequest(BaseModel):
    notes: Optional[str] = Field(default=None, description="Optional operator notes")


class QueueResolutionRequest(BaseModel):
    action: str = Field(description="Action to perform: APPROVE, REJECT, or MERGE")
    notes: Optional[str] = Field(default=None, description="Optional operator notes")


class ConflictResolutionRequest(BaseModel):
    resolved_value: str = Field(description="The authoritative resolved value")
    resolution_strategy: Optional[str] = Field(default="MANUAL_OFFICIAL_OVERRIDE", description="Resolution strategy")
    notes: Optional[str] = Field(default=None, description="Optional resolution notes")


class OpportunityVerificationOverview(BaseModel):
    opportunity_id: str
    title: str
    verification_status: str
    verification_confidence: float
    source_count: int
    official_source_present: bool
    last_verified_at: Optional[datetime] = None
    sources: List[OpportunitySourceResponse] = []
    verified_fields: List[VerifiedFieldResponse] = []
    conflicts: List[VerificationConflictResponse] = []
