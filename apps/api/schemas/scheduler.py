"""
Pydantic Schemas for Scheduler Observability API (Phase 5A)
"""
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict


class ScheduledJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    source_id: str
    source_slug: Optional[str] = None
    source_name: Optional[str] = None
    status: str
    started_at: datetime
    finished_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    items_discovered: int = 0
    items_processed: int = 0
    error_message: Optional[str] = None
    created_at: datetime


class SchedulerSourcesStatus(BaseModel):
    total: int
    active: int
    scheduler_enabled: int
    due_for_polling: int


class SchedulerStatusResponse(BaseModel):
    running: bool
    timezone: str
    scheduler_jobs_count: int
    active_jobs: List[str] = []
    sources: SchedulerSourcesStatus
    recent_successful_polls_24h: int = 0
    recent_failed_polls_24h: int = 0


class PollTriggerResponse(BaseModel):
    success: bool
    source_slug: str
    source_name: Optional[str] = None
    job_id: Optional[str] = None
    status: str
    items_discovered: int = 0
    items_processed: int = 0
    duration_ms: Optional[int] = None
    error_message: Optional[str] = None


class PollAllTriggerResponse(BaseModel):
    success: bool
    total_eligible: int
    triggered_sources: List[str]
    message: str
