"""
Pydantic Schemas for OrganizationAlias
"""
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class OrganizationAliasBase(BaseModel):
    organization_id: str
    alias: str = Field(..., min_length=1, max_length=255)
    normalized_alias: str = Field(..., min_length=1, max_length=255)


class OrganizationAliasCreate(BaseModel):
    alias: str = Field(..., min_length=1, max_length=255)


class OrganizationAliasRead(OrganizationAliasBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
    updated_at: datetime
