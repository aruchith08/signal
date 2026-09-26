"""
Pydantic Schemas for ProgramWatch, Aliases, Keywords, Sources, and Matches
"""
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field
from shared.constants import WatchPriority, WatchMatchLevel
from apps.api.schemas.organization import OrganizationRead
from apps.api.schemas.source import SourceRead
from apps.api.schemas.discovery import DiscoveryRead


class ProgramWatchAliasBase(BaseModel):
    alias: str = Field(..., min_length=1, max_length=255)


class ProgramWatchAliasCreate(ProgramWatchAliasBase):
    pass


class ProgramWatchAliasRead(ProgramWatchAliasBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    program_watch_id: str
    normalized_alias: str
    created_at: datetime


class ProgramWatchKeywordBase(BaseModel):
    keyword: str = Field(..., min_length=1, max_length=255)
    weight: float = Field(default=1.0, ge=0.0, le=1.0)
    is_distinctive: bool = True


class ProgramWatchKeywordCreate(ProgramWatchKeywordBase):
    pass


class ProgramWatchKeywordRead(ProgramWatchKeywordBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    program_watch_id: str
    normalized_keyword: str
    created_at: datetime


class ProgramWatchSourceBase(BaseModel):
    source_id: Optional[str] = None
    url: Optional[str] = None
    priority: int = 1
    is_active: bool = True


class ProgramWatchSourceCreate(ProgramWatchSourceBase):
    pass


class ProgramWatchSourceRead(ProgramWatchSourceBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    program_watch_id: str
    created_at: datetime
    source: Optional[SourceRead] = None


class ProgramWatchBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    canonical_name: Optional[str] = Field(None, max_length=255)
    organization_id: Optional[str] = None
    description: Optional[str] = None
    priority: WatchPriority = WatchPriority.HIGH
    is_active: bool = True


class ProgramWatchCreate(ProgramWatchBase):
    aliases: Optional[List[ProgramWatchAliasCreate]] = None
    keywords: Optional[List[ProgramWatchKeywordCreate]] = None
    sources: Optional[List[ProgramWatchSourceCreate]] = None


class ProgramWatchUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    canonical_name: Optional[str] = Field(None, max_length=255)
    organization_id: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[WatchPriority] = None
    is_active: Optional[bool] = None


class ProgramWatchRead(ProgramWatchBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    canonical_name: str
    created_at: datetime
    updated_at: datetime


class ProgramWatchDetailRead(ProgramWatchRead):
    organization: Optional[OrganizationRead] = None
    aliases: List[ProgramWatchAliasRead] = []
    keywords: List[ProgramWatchKeywordRead] = []
    sources: List[ProgramWatchSourceRead] = []


class ProgramWatchMatchRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    program_watch_id: str
    raw_discovery_id: str
    match_score: float
    match_level: str
    match_reason: str
    matched_terms: List[str]
    created_at: datetime


class ProgramWatchMatchDetailRead(ProgramWatchMatchRead):
    program_watch: Optional[ProgramWatchRead] = None
    raw_discovery: Optional[DiscoveryRead] = None
