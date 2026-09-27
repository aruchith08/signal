"""
Dashboard API Router — Provides aggregation statistics, overview, and recent activity for monitoring UI
"""
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import desc, func, select, or_
from sqlalchemy.orm import selectinload

from apps.api.database import get_db
from apps.api.models.discovery import RawDiscovery
from apps.api.models.event import OpportunityEvent
from apps.api.models.opportunity import Opportunity
from apps.api.models.organization import Organization
from apps.api.models.snapshot import SourceSnapshot
from apps.api.models.source import Source
from apps.api.models.user import User
from apps.api.models.verification import VerificationReview
from apps.api.schemas.dashboard import (
    DashboardOverviewResponse,
    DeadlineApproachingItem,
    PersonalizedOpportunityItem,
    TopPriorityItem,
)
from apps.api.schemas.event import EventRead
from apps.api.schemas.opportunity import OpportunityRead
from services.personalization.relevance_engine import PersonalizationEngine
from shared.constants import SourceHealthStatus

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


class DashboardSourcesSummary(BaseModel):
    total_sources: int
    healthy_sources: int
    degraded_sources: int
    failing_sources: int
    sources_checked_today: int
    new_discoveries_today: int
    changes_detected_today: int


class ActivityItem(BaseModel):
    timestamp: datetime
    activity_type: str
    title: str
    description: str
    source_name: Optional[str] = None
    opportunity_id: Optional[str] = None


def _to_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _format_urgency_label(deadline_dt: Optional[datetime]) -> str:
    if not deadline_dt:
        return "Ongoing"
    deadline_dt = _to_utc(deadline_dt)
    now = datetime.now(timezone.utc)
    diff = deadline_dt - now
    if diff.total_seconds() < 0:
        return "Closed"
    hours = int(diff.total_seconds() // 3600)
    days = diff.days
    if hours < 24:
        return f"{hours} hours left"
    elif days == 1:
        return "1 day left"
    else:
        return f"{days} days left"


@router.get("/overview", response_model=DashboardOverviewResponse)
@router.get("", response_model=DashboardOverviewResponse)
async def get_dashboard_overview(
    user_id: Optional[str] = Query(None, description="Active user ID for personalized scoring"),
    db: AsyncSession = Depends(get_db),
):
    """
    Aggregated single-call intelligence overview for the Signal Dashboard.
    Returns:
    - top_priority: Highest urgency/relevance opportunity
    - for_you: Personalized recommendations with relevance scores
    - recent_announcements: Latest opportunities added to the network
    - deadlines_approaching: Upcoming opportunities sorted by deadline
    - recent_updates: Chronological stream of lifecycle updates
    - stats: High-level network metrics
    """
    now_utc = datetime.now(timezone.utc)

    # 1. Load active user if requested or find default
    user = None
    if user_id and isinstance(user_id, str):
        u_stmt = (
            select(User)
            .options(
                selectinload(User.profile),
                selectinload(User.interests),
                selectinload(User.skills),
                selectinload(User.preferences),
            )
            .where(User.id == user_id)
        )
        user = (await db.execute(u_stmt)).scalars().first()
    if not user:
        u_stmt = (
            select(User)
            .options(
                selectinload(User.profile),
                selectinload(User.interests),
                selectinload(User.skills),
                selectinload(User.preferences),
            )
            .order_by(User.created_at.asc())
        )
        user = (await db.execute(u_stmt)).scalars().first()

    # 2. Stats
    total_opps = (await db.execute(select(func.count(Opportunity.id)))).scalar() or 0
    total_sources = (await db.execute(select(func.count(Source.id)))).scalar() or 0
    healthy_sources = (
        await db.execute(
            select(func.count(Source.id)).where(Source.status == SourceHealthStatus.HEALTHY.value)
        )
    ).scalar() or 0
    verified_opps = (
        await db.execute(
            select(func.count(Opportunity.id)).where(
                Opportunity.verification_status.in_(["verified", "likely_verified"])
            )
        )
    ).scalar() or 0
    pending_reviews = (
        await db.execute(
            select(func.count(VerificationReview.id)).where(VerificationReview.status == "pending")
        )
    ).scalar() or 0

    active_events = (
        await db.execute(
            select(func.count(OpportunityEvent.id)).where(
                (OpportunityEvent.deadline_date == None) | (OpportunityEvent.deadline_date >= now_utc - timedelta(days=1))
            )
        )
    ).scalar() or 0
    critical_deadlines = (
        await db.execute(
            select(func.count(OpportunityEvent.id)).where(
                OpportunityEvent.deadline_date != None,
                OpportunityEvent.deadline_date >= now_utc - timedelta(days=1),
                OpportunityEvent.deadline_date <= now_utc + timedelta(days=14),
            )
        )
    ).scalar() or 0

    stats = {
        "opportunities_tracked": total_opps,
        "sources_online": healthy_sources,
        "sources_total": total_sources,
        "verified_opportunities": verified_opps,
        "pending_reviews": pending_reviews,
        "total_tracked": total_opps,
        "active_events": active_events,
        "verified_sources": total_sources,
        "critical_deadlines": critical_deadlines,
    }

    # 3. Deadlines Approaching (Events with deadline_date in future)
    deadlines_stmt = (
        select(OpportunityEvent, Opportunity)
        .join(Opportunity, Opportunity.id == OpportunityEvent.opportunity_id)
        .options(selectinload(Opportunity.organization))
        .where(OpportunityEvent.deadline_date != None)
        .where(OpportunityEvent.deadline_date >= now_utc - timedelta(days=1))
        .order_by(OpportunityEvent.deadline_date.asc())
        .limit(6)
    )
    deadlines_raw = (await db.execute(deadlines_stmt)).all()
    deadlines_approaching: List[DeadlineApproachingItem] = []
    for ev, opp in deadlines_raw:
        deadlines_approaching.append(
            DeadlineApproachingItem(
                opportunity_id=opp.id,
                opportunity_title=opp.title,
                organization_name=opp.organization.name if opp.organization else None,
                category=opp.category,
                deadline_date=ev.deadline_date,
                urgency_label=_format_urgency_label(ev.deadline_date),
                is_critical=ev.is_critical,
            )
        )

    # 4. Recent Announcements (Newest opportunities)
    recent_opps_stmt = (
        select(Opportunity)
        .options(
            selectinload(Opportunity.organization),
            selectinload(Opportunity.source),
            selectinload(Opportunity.events),
            selectinload(Opportunity.aliases),
        )
        .order_by(Opportunity.created_at.desc())
        .limit(6)
    )
    recent_opps = (await db.execute(recent_opps_stmt)).scalars().all()
    recent_announcements = [OpportunityRead.model_validate(o) for o in recent_opps]

    # 5. For You (Personalized scored feed)
    for_you: List[PersonalizedOpportunityItem] = []
    candidate_opps_stmt = (
        select(Opportunity)
        .options(
            selectinload(Opportunity.organization),
            selectinload(Opportunity.source),
            selectinload(Opportunity.events),
            selectinload(Opportunity.aliases),
        )
        .order_by(Opportunity.confidence_score.desc(), Opportunity.created_at.desc())
        .limit(15)
    )
    candidate_opps = (await db.execute(candidate_opps_stmt)).scalars().all()

    engine = PersonalizationEngine(db) if user else None
    scored_items = []
    for opp in candidate_opps:
        nearest_deadline = None
        for ev in opp.events:
            ev_dl = _to_utc(ev.deadline_date)
            if ev_dl and ev_dl >= now_utc - timedelta(days=1):
                if nearest_deadline is None or ev_dl < nearest_deadline:
                    nearest_deadline = ev_dl

        if user and engine:
            eval_res = await engine.evaluate_relevance(user, opp)
            score = eval_res.score
            elig = eval_res.eligibility_status.value if hasattr(eval_res.eligibility_status, "value") else str(eval_res.eligibility_status)
            factors = eval_res.reasons
        else:
            score = opp.confidence_score or 75
            elig = "ELIGIBLE"
            cat_display = opp.category.replace('_', ' ').title()
            factors = [f"Category: {cat_display}", f"Confidence: {opp.confidence_score}%"]

        scored_items.append((
            score,
            PersonalizedOpportunityItem(
                opportunity=OpportunityRead.model_validate(opp),
                relevance_score=score,
                eligibility=elig,
                match_factors=factors[:3],
                nearest_deadline=nearest_deadline,
                urgency_label=_format_urgency_label(nearest_deadline),
            ),
            opp,
        ))

    # Sort descending by relevance score
    scored_items.sort(key=lambda x: x[0], reverse=True)
    for_you = [item[1] for item in scored_items[:8]]

    # 6. Top Priority Item (Best match with urgency or highest relevance)
    top_priority = None
    if scored_items:
        _, top_item, top_opp = scored_items[0]
        # Find matching event if any from ORM model
        top_event = None
        for ev in top_opp.events:
            if ev.deadline_date:
                top_event = EventRead.model_validate(ev)
                break

        why_text = (
            top_item.match_factors[0]
            if top_item.match_factors
            else "High priority opportunity matching your intelligence profile."
        )

        top_priority = TopPriorityItem(
            opportunity=top_item.opportunity,
            event=top_event,
            urgency_label=top_item.urgency_label or "Upcoming",
            relevance_score=top_item.relevance_score,
            why_it_matters=why_text,
        )

    # 7. Recent Updates
    activity_items = await get_dashboard_activity(limit=8, db=db)
    recent_updates = [a.model_dump() for a in activity_items]

    return DashboardOverviewResponse(
        top_priority=top_priority,
        for_you=for_you,
        recent_announcements=recent_announcements,
        deadlines_approaching=deadlines_approaching,
        recent_updates=recent_updates,
        stats=stats,
    )


@router.get("/sources", response_model=DashboardSourcesSummary)
async def get_dashboard_sources(
    db: AsyncSession = Depends(get_db),
):
    """Aggregate health and activity metrics across all monitored sources."""
    total_sources = (await db.execute(select(func.count(Source.id)))).scalar() or 0
    healthy = (
        await db.execute(
            select(func.count(Source.id)).where(Source.status == SourceHealthStatus.HEALTHY.value)
        )
    ).scalar() or 0
    degraded = (
        await db.execute(
            select(func.count(Source.id)).where(Source.status == SourceHealthStatus.DEGRADED.value)
        )
    ).scalar() or 0
    failing = (
        await db.execute(
            select(func.count(Source.id)).where(Source.status == SourceHealthStatus.FAILING.value)
        )
    ).scalar() or 0

    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    checked_today = (
        await db.execute(
            select(func.count(Source.id)).where(Source.last_polled_at >= today_start)
        )
    ).scalar() or 0

    discoveries_today = (
        await db.execute(
            select(func.count(RawDiscovery.id)).where(RawDiscovery.created_at >= today_start)
        )
    ).scalar() or 0

    changes_today = (
        await db.execute(
            select(func.count(SourceSnapshot.id)).where(
                SourceSnapshot.created_at >= today_start,
                SourceSnapshot.status == "changed",
            )
        )
    ).scalar() or 0

    return DashboardSourcesSummary(
        total_sources=total_sources,
        healthy_sources=healthy,
        degraded_sources=degraded,
        failing_sources=failing,
        sources_checked_today=checked_today,
        new_discoveries_today=discoveries_today,
        changes_detected_today=changes_today,
    )


@router.get("/activity", response_model=List[ActivityItem])
async def get_dashboard_activity(
    limit: int = 25,
    db: AsyncSession = Depends(get_db),
):
    """Chronological live activity feed of recent discoveries and lifecycle events."""
    events_stmt = (
        select(OpportunityEvent)
        .order_by(desc(OpportunityEvent.event_date), desc(OpportunityEvent.created_at))
        .limit(limit)
    )
    events = (await db.execute(events_stmt)).scalars().all()

    disc_stmt = (
        select(RawDiscovery)
        .order_by(desc(RawDiscovery.created_at))
        .limit(limit)
    )
    discoveries = (await db.execute(disc_stmt)).scalars().all()

    activities: List[ActivityItem] = []

    for ev in events:
        activities.append(
            ActivityItem(
                timestamp=ev.event_date or ev.created_at,
                activity_type=f"event:{ev.event_type}",
                title=ev.title,
                description=ev.description or f"Lifecycle event '{ev.event_type}' recorded",
                source_name=None,
                opportunity_id=ev.opportunity_id,
            )
        )

    for disc in discoveries:
        activities.append(
            ActivityItem(
                timestamp=disc.created_at,
                activity_type=f"discovery:{disc.status}",
                title=disc.raw_title,
                description=disc.processing_reason or f"Discovery status: {disc.status}",
                source_name=None,
                opportunity_id=disc.opportunity_id,
            )
        )

    activities.sort(key=lambda a: a.timestamp, reverse=True)
    return activities[:limit]


audit_router = APIRouter(tags=["Audit Logs"])


@audit_router.get("/audit-logs", response_model=List[ActivityItem], include_in_schema=False)
async def get_audit_logs_alias(
    limit: int = 25,
    db: AsyncSession = Depends(get_db),
):
    """Direct alias for /audit-logs pointing to activity stream."""
    return await get_dashboard_activity(limit=limit, db=db)


class OperatorDiagnostics(BaseModel):
    timestamp: datetime
    sources: Dict[str, int]
    verification: Dict[str, int]
    notifications: Dict[str, int]
    scheduler_running: bool
    active_jobs_count: int


@router.get("/diagnostics", response_model=OperatorDiagnostics, summary="Consolidated operator diagnostics")
async def get_operator_diagnostics(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Consolidated operational health, queue depths, and failure counts for administrators."""
    from apps.api.models.verification import VerificationReview, VerificationConflict
    from apps.api.models.notification_delivery import NotificationDelivery
    from services.scheduler.scheduler import get_scheduler

    total_sources = (await db.execute(select(func.count(Source.id)))).scalar() or 0
    failing_sources = (
        await db.execute(select(func.count(Source.id)).where(Source.status == SourceHealthStatus.FAILING.value))
    ).scalar() or 0
    healthy_sources = (
        await db.execute(select(func.count(Source.id)).where(Source.status == SourceHealthStatus.HEALTHY.value))
    ).scalar() or 0

    open_reviews = (
        await db.execute(select(func.count(VerificationReview.id)).where(VerificationReview.status == "open"))
    ).scalar() or 0
    open_conflicts = (
        await db.execute(select(func.count(VerificationConflict.id)).where(VerificationConflict.status == "open"))
    ).scalar() or 0

    since_24h = datetime.now(timezone.utc) - timedelta(hours=24)
    failed_deliveries = (
        await db.execute(
            select(func.count(NotificationDelivery.id)).where(
                NotificationDelivery.status == "failed",
                NotificationDelivery.created_at >= since_24h,
            )
        )
    ).scalar() or 0

    scheduler = get_scheduler(request.app)
    is_running = getattr(scheduler, "running", False)
    try:
        active_jobs = len(scheduler.get_jobs())
    except Exception:
        active_jobs = 0

    return OperatorDiagnostics(
        timestamp=datetime.now(timezone.utc),
        sources={
            "total": total_sources,
            "healthy": healthy_sources,
            "failing": failing_sources,
        },
        verification={
            "open_reviews": open_reviews,
            "open_conflicts": open_conflicts,
        },
        notifications={
            "failed_deliveries_last_24h": failed_deliveries,
        },
        scheduler_running=is_running,
        active_jobs_count=active_jobs,
    )

