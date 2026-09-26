"""
Pydantic Schemas for Skill and UserSkill
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class SkillBase(BaseModel):
    name: str
    slug: str
    category: Optional[str] = None


class SkillCreate(BaseModel):
    name: str
    category: Optional[str] = None


class SkillRead(SkillBase):
    id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserSkillBase(BaseModel):
    proficiency_level: str = "intermediate"  # beginner, intermediate, advanced, expert


class UserSkillCreate(UserSkillBase):
    skill_name: str
    category: Optional[str] = None


class UserSkillRead(UserSkillBase):
    id: str
    user_id: str
    skill_id: str
    skill: SkillRead
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
