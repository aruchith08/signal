"""
Health and Status Check Router
Provides comprehensive system health, Kubernetes/Docker liveness, and readiness probes.
"""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from apps.api.database import get_db
from apps.api.config import settings
from services.intelligence.router import ai_router

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("", summary="Comprehensive system health check")
@router.get("/", include_in_schema=False)
async def get_health(db: AsyncSession = Depends(get_db)):
    """System health check endpoint verifying database connectivity and AI gateway status."""
    db_status = "healthy"
    try:
        await db.execute(text("SELECT 1"))
    except Exception as exc:
        db_status = f"unhealthy: {str(exc)}"

    ai_provider = settings.AI_PRIMARY_PROVIDER
    provider_inst = ai_router.get_provider(ai_provider)
    ai_status = "available" if (provider_inst and await provider_inst.is_available()) else "fallback_active"

    return {
        "status": "healthy" if "unhealthy" not in db_status else "degraded",
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "database": db_status,
        "ai_gateway": {
            "primary_provider": ai_provider,
            "status": ai_status,
        },
    }


@router.get("/live", summary="Liveness probe for process uptime")
async def liveness_check():
    """Liveness probe: returns 200 immediately to confirm the HTTP server process is responsive."""
    return {
        "status": "alive",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/ready", summary="Readiness probe for dependency verification")
async def readiness_check(db: AsyncSession = Depends(get_db)):
    """Readiness probe: validates database connectivity; returns 503 Service Unavailable if database is unreachable."""
    try:
        await db.execute(text("SELECT 1"))
        return {
            "status": "ready",
            "database": "connected",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as exc:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "not_ready",
                "database": f"unreachable: {str(exc)}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )
