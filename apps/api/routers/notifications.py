"""
Notifications and Telegram Webhook Router
"""
import logging
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from apps.api.database import get_db
from apps.api.models.user import User
from apps.api.models.opportunity import Opportunity
from apps.api.models.event import OpportunityEvent
from apps.api.models.notification import Notification
from apps.api.models.notification_delivery import NotificationDelivery
from apps.api.schemas.notification import (
    NotificationRead,
    NotificationDeliveryRead,
    ProviderStatusListResponse,
    DeliveryListResponse,
    DeliveryRetryResponse,
)
from services.notifications.decision_engine import NotificationDecisionEngine
from services.notifications.dispatcher import NotificationDispatcher
from services.notifications.telegram_bot import TelegramBotHandler
from services.notifications.provider_registry import provider_registry
from services.notifications.retry import NotificationRetryEngine, MAX_ATTEMPTS

logger = logging.getLogger("signal.api.notifications")
router = APIRouter(prefix="/notifications", tags=["Notifications & Alerts"])


class TestNotificationPayload(BaseModel):
    user_id: str
    opportunity_id: str
    event_id: Optional[str] = None
    force_instant: bool = False


class TelegramWebhookUpdate(BaseModel):
    update_id: int
    message: Optional[Dict[str, Any]] = None


@router.post("/test", response_model=Dict[str, Any])
async def trigger_test_notification(
    payload: TestNotificationPayload,
    db: AsyncSession = Depends(get_db),
):
    """
    Safely tests the entire end-to-end personalization and alert dispatch pipeline.
    Evaluates eligibility, relevance score, anti-fatigue checks, and records an audit log.
    """
    # 1. Load User
    user_stmt = (
        select(User)
        .where(User.id == payload.user_id)
        .options(
            selectinload(User.profile),
            selectinload(User.interests),
            selectinload(User.skills),
            selectinload(User.preferences),
        )
    )
    user = (await db.execute(user_stmt)).scalars().first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # 2. Load Opportunity
    opp_stmt = (
        select(Opportunity)
        .where(Opportunity.id == payload.opportunity_id)
        .options(
            selectinload(Opportunity.organization),
            selectinload(Opportunity.events),
        )
    )
    opp = (await db.execute(opp_stmt)).scalars().first()
    if not opp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Opportunity not found")

    # 3. Load Event (or latest event)
    event = None
    if payload.event_id:
        event_stmt = select(OpportunityEvent).where(OpportunityEvent.id == payload.event_id)
        event = (await db.execute(event_stmt)).scalars().first()
    elif opp.events:
        event = opp.events[-1]

    # 4. Decision Engine
    decision_engine = NotificationDecisionEngine(db)
    decision = await decision_engine.evaluate(user=user, opportunity=opp, event=event)

    if payload.force_instant and decision.relevance_result and decision.relevance_result.score >= 50:
        decision.should_notify = True
        from shared.constants import DeliveryMode
        decision.delivery_mode = DeliveryMode.INSTANT

    # 5. Dispatcher
    dispatcher = NotificationDispatcher(db)
    notification = await dispatcher.dispatch(
        user=user,
        opportunity=opp,
        decision=decision,
        event=event,
    )
    await db.commit()

    return {
        "status": "success",
        "decision": decision.to_dict(),
        "notification_id": notification.id if notification else None,
        "notification_status": notification.status if notification else "none",
    }


@router.post("/telegram/webhook", response_model=Dict[str, Any])
async def handle_telegram_webhook(
    update: Dict[str, Any],
    db: AsyncSession = Depends(get_db),
):
    """
    Handles incoming Telegram bot updates and commands (/start, /status, /preferences, /subscribe, etc.).
    """
    message = update.get("message")
    if not message:
        return {"status": "ok", "action": "ignored"}

    chat = message.get("chat", {})
    chat_id = str(chat.get("id"))
    from_user = message.get("from", {})
    user_id = str(from_user.get("id", chat_id))
    username = from_user.get("username")
    full_name = f"{from_user.get('first_name', '')} {from_user.get('last_name', '')}".strip()
    text = message.get("text", "")

    bot_handler = TelegramBotHandler(db)
    reply_text = await bot_handler.handle_command(
        chat_id=chat_id,
        command_text=text,
        telegram_user_id=user_id,
        username=username,
        full_name=full_name,
    )
    await db.commit()

    return {
        "status": "ok",
        "chat_id": chat_id,
        "reply": reply_text,
    }


@router.get("/providers/status", response_model=ProviderStatusListResponse)
async def get_providers_status():
    """
    Returns the real-time operational and connectivity status of all registered notification providers.
    """
    statuses = await provider_registry.get_provider_status()
    return {"providers": statuses}


@router.get("/deliveries", response_model=DeliveryListResponse)
async def list_notification_deliveries(
    user_id: Optional[str] = Query(None, description="Filter deliveries by user ID"),
    notification_id: Optional[str] = Query(None, description="Filter by parent notification ID"),
    channel: Optional[str] = Query(None, description="Filter by notification channel"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by delivery status"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieves paginated audit history of NotificationDelivery records with optional filtering.
    """
    stmt = select(NotificationDelivery)
    count_stmt = select(func.count(NotificationDelivery.id))

    if notification_id:
        stmt = stmt.where(NotificationDelivery.notification_id == notification_id)
        count_stmt = count_stmt.where(NotificationDelivery.notification_id == notification_id)
    if channel:
        stmt = stmt.where(NotificationDelivery.channel == channel)
        count_stmt = count_stmt.where(NotificationDelivery.channel == channel)
    if status_filter:
        stmt = stmt.where(NotificationDelivery.status == status_filter)
        count_stmt = count_stmt.where(NotificationDelivery.status == status_filter)
    if user_id:
        stmt = stmt.join(Notification, Notification.id == NotificationDelivery.notification_id).where(Notification.user_id == user_id)
        count_stmt = count_stmt.join(Notification, Notification.id == NotificationDelivery.notification_id).where(Notification.user_id == user_id)

    total = (await db.execute(count_stmt)).scalar() or 0
    offset = (page - 1) * page_size
    stmt = stmt.order_by(NotificationDelivery.created_at.desc()).offset(offset).limit(page_size)

    items = (await db.execute(stmt)).scalars().all()

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("/deliveries/{delivery_id}/retry", response_model=DeliveryRetryResponse)
async def retry_delivery_endpoint(
    delivery_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Triggers an immediate retry attempt for an existing failed NotificationDelivery record.
    """
    stmt = select(NotificationDelivery).where(NotificationDelivery.id == delivery_id)
    delivery = (await db.execute(stmt)).scalars().first()
    if not delivery:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="NotificationDelivery not found")

    if delivery.attempt_count >= MAX_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Delivery has reached maximum allowed attempts ({MAX_ATTEMPTS})",
        )

    retry_engine = NotificationRetryEngine()
    success = await retry_engine.retry_delivery(delivery_id, db)
    await db.commit()

    # Re-fetch updated delivery state
    updated_stmt = select(NotificationDelivery).where(NotificationDelivery.id == delivery_id)
    updated_delivery = (await db.execute(updated_stmt)).scalars().first()

    return {
        "delivery_id": delivery_id,
        "success": success,
        "status": updated_delivery.status if updated_delivery else "unknown",
        "attempt_count": updated_delivery.attempt_count if updated_delivery else delivery.attempt_count,
        "error_message": updated_delivery.error_message if updated_delivery else None,
    }
