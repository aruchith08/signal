"""
Pydantic Schemas for UserNotificationPreference
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class UserNotificationPreferenceBase(BaseModel):
    enabled: bool = True
    min_relevance_score: int = Field(default=70, ge=0, le=100)
    instant_alerts_enabled: bool = True
    digest_enabled: bool = False
    quiet_hours_enabled: bool = False
    quiet_hours_start: str = "22:30"
    quiet_hours_end: str = "07:30"
    timezone: str = "Asia/Kolkata"
    max_alerts_per_day: int = Field(default=10, ge=1, le=100)
    telegram_chat_id: Optional[str] = None
    telegram_user_id: Optional[str] = None
    telegram_username: Optional[str] = None


class UserNotificationPreferenceUpdate(BaseModel):
    enabled: Optional[bool] = None
    min_relevance_score: Optional[int] = Field(default=None, ge=0, le=100)
    instant_alerts_enabled: Optional[bool] = None
    digest_enabled: Optional[bool] = None
    quiet_hours_enabled: Optional[bool] = None
    quiet_hours_start: Optional[str] = None
    quiet_hours_end: Optional[str] = None
    timezone: Optional[str] = None
    max_alerts_per_day: Optional[int] = Field(default=None, ge=1, le=100)
    telegram_chat_id: Optional[str] = None
    telegram_user_id: Optional[str] = None
    telegram_username: Optional[str] = None


class UserNotificationPreferenceRead(UserNotificationPreferenceBase):
    id: str
    user_id: str
    telegram_linked_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
