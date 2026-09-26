"""
Pydantic Schemas for Notification
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class NotificationBase(BaseModel):
    user_id: str
    opportunity_id: str
    event_id: Optional[str] = None
    channel: str = "telegram"
    priority: str = "medium"
    status: str = "pending"
    delivery_mode: str = "instant"
    relevance_score: Optional[float] = None
    decision_reason: Optional[str] = None
    message: str


class NotificationCreate(NotificationBase):
    pass


class NotificationRead(NotificationBase):
    id: str
    error_message: Optional[str] = None
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class NotificationDeliveryRead(BaseModel):
    id: str
    notification_id: str
    channel: str
    status: str
    attempt_count: int
    last_attempt_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    error_message: Optional[str] = None
    channel_identifier: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProviderStatusRead(BaseModel):
    channel: str
    enabled: bool
    healthy: bool
    provider_name: Optional[str] = None
    details: Optional[dict] = None


class ProviderStatusListResponse(BaseModel):
    providers: list[ProviderStatusRead]


class DeliveryListResponse(BaseModel):
    items: list[NotificationDeliveryRead]
    total: int
    page: int
    page_size: int


class DeliveryRetryResponse(BaseModel):
    delivery_id: str
    success: bool
    status: str
    attempt_count: int
    error_message: Optional[str] = None
