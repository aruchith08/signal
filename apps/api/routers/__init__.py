from apps.api.routers.health import router as health_router
from apps.api.routers.organizations import router as organizations_router
from apps.api.routers.sources import router as sources_router
from apps.api.routers.opportunities import router as opportunities_router
from apps.api.routers.events import router as events_router
from apps.api.routers.ingestion import router as ingestion_router
from apps.api.routers.discoveries import router as discoveries_router
from apps.api.routers.program_watches import router as program_watches_router
from apps.api.routers.dashboard import router as dashboard_router, audit_router
from apps.api.routers.users import router as users_router
from apps.api.routers.notifications import router as notifications_router
from apps.api.routers.verification import router as verification_router
from apps.api.routers.scheduler import router as scheduler_router
from apps.api.routers.auth import router as auth_router

__all__ = [
    "health_router",
    "auth_router",
    "organizations_router",
    "sources_router",
    "opportunities_router",
    "events_router",
    "ingestion_router",
    "discoveries_router",
    "program_watches_router",
    "dashboard_router",
    "audit_router",
    "users_router",
    "notifications_router",
    "verification_router",
    "scheduler_router",
]

