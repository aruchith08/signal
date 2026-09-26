"""
Pydantic Schemas for Organization
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class OrganizationBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    website: Optional[str] = Field(None, max_length=512)
    logo_url: Optional[str] = Field(None, max_length=512)
    description: Optional[str] = None
    is_verified: bool = False


class OrganizationCreate(OrganizationBase):
    slug: Optional[str] = Field(None, max_length=255)


class OrganizationUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    website: Optional[str] = None
    logo_url: Optional[str] = None
    description: Optional[str] = None
    is_verified: Optional[bool] = None


class OrganizationRead(OrganizationBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    slug: str
    created_at: datetime
    updated_at: datetime
