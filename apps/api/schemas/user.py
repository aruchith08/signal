"""
Pydantic Schemas for User, UserProfile, and UserInterest
"""
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field, computed_field


class UserProfileBase(BaseModel):
    education_level: Optional[str] = None
    degree: Optional[str] = None
    branch: Optional[str] = None
    current_year: Optional[int] = None
    graduation_year: Optional[int] = None
    country: str = "India"
    state: Optional[str] = None
    timezone: str = "Asia/Kolkata"
    career_interests: Optional[str] = None
    preferred_opportunity_types: Optional[str] = None
    bio: Optional[str] = None


class UserProfileCreate(UserProfileBase):
    pass


class UserProfileUpdate(BaseModel):
    education_level: Optional[str] = None
    degree: Optional[str] = None
    branch: Optional[str] = None
    current_year: Optional[int] = None
    graduation_year: Optional[int] = None
    country: Optional[str] = None
    state: Optional[str] = None
    timezone: Optional[str] = None
    career_interests: Optional[str] = None
    preferred_opportunity_types: Optional[str] = None
    bio: Optional[str] = None


class UserProfileRead(UserProfileBase):
    id: str
    user_id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserInterestBase(BaseModel):
    category: str
    tag: str
    weight: float = Field(default=1.0, ge=0.0, le=1.0)


class UserInterestCreate(UserInterestBase):
    pass


class UserInterestUpdate(BaseModel):
    weight: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    category: Optional[str] = None
    tag: Optional[str] = None


class UserInterestRead(UserInterestBase):
    id: str
    user_id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserBase(BaseModel):
    email: str
    username: str
    full_name: Optional[str] = None
    role: str = "user"
    is_active: bool = True
    is_superuser: bool = False


class UserCreate(UserBase):
    password: Optional[str] = None



class UserUpdate(BaseModel):
    email: Optional[str] = None
    username: Optional[str] = None
    full_name: Optional[str] = None
    is_active: Optional[bool] = None


class UserRead(UserBase):
    id: str
    created_at: datetime
    updated_at: datetime
    profile: Optional[UserProfileRead] = None
    interests: List[UserInterestRead] = []

    model_config = ConfigDict(from_attributes=True)

    @computed_field
    @property
    def name(self) -> str:
        return self.full_name or self.username

    @computed_field
    @property
    def education_level(self) -> Optional[str]:
        return self.profile.education_level if self.profile else None

    @computed_field
    @property
    def graduation_year(self) -> Optional[int]:
        return self.profile.graduation_year if self.profile else None

    @computed_field
    @property
    def relevance_threshold(self) -> float:
        return 0.70
