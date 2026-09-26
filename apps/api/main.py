"""
SIGNAL 📡 — FastAPI Application Entrypoint
"""
import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse

from apps.api.config import settings
from apps.api.database import init_db, engine, is_serverless
from apps.api.routers import (
    health_router,
    organizations_router,
    sources_router,
    opportunities_router,
    events_router,
    ingestion_router,
    discoveries_router,
    program_watches_router,
    dashboard_router,
    audit_router,
    users_router,
    notifications_router,
    verification_router,
    scheduler_router,
    auth_router,
)
from services.scheduler.scheduler import schedule_jobs


# Setup logging
logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("signal")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle hooks: initialize database and clean up resources."""
    logger.info("📡 Starting SIGNAL Opportunity Intelligence Platform...")
    try:
        # Initialize DB tables for development/testing
        try:
            await init_db()
            logger.info("Database schema initialized.")
        except Exception as exc:
            logger.error(f"Database initialization error during startup: {exc}")

        # Initialize default sources (e.g. Unstop, Devfolio) idempotently
        try:
            from apps.api.database import AsyncSessionLocal
            from services.sources.registry import ensure_devfolio_source, ensure_unstop_source, ensure_source
            async with AsyncSessionLocal() as session:
                await ensure_unstop_source(session)
                await ensure_devfolio_source(session)
                for slug in ["codeforces", "sih", "gsoc", "atcoder", "github-blog", "kaggle", "huggingface"]:
                    await ensure_source(slug, session)
                await session.commit()
            logger.info("Default opportunity sources registered.")
        except Exception as exc:
            logger.warning(f"Could not register default sources during startup: {exc}")

        # Start scheduler after DB init if enabled and not in serverless mode
        if settings.ENABLE_SCHEDULER and not is_serverless:
            schedule_jobs(app)
        else:
            logger.info("Scheduler skipped (serverless or disabled mode).")
    except Exception as exc:
        logger.critical(f"FATAL error in lifespan startup: {exc}", exc_info=True)

    try:
        yield
    finally:
        logger.info("Shutting down SIGNAL Platform...")
        # Shutdown scheduler if running
        scheduler = getattr(app.state, "scheduler", None)
        if scheduler:
            try:
                scheduler.shutdown(wait=False)
            except Exception:
                pass
        try:
            await engine.dispose()
        except Exception:
            pass


app = FastAPI(
    title=f"{settings.APP_NAME} 📡 — Opportunity Intelligence Platform",
    description="""
    ## Personal Opportunity Intelligence Network

    SIGNAL monitors, extracts, verifies, and alerts students and developers about
    important tech opportunities across:
    * **Competitive Programming** (CodeChef, Codeforces, LeetCode)
    * **Hackathons** (Devfolio, Unstop, SIH)
    * **Major Company Programs** (TCS CodeVita, Flipkart GRiD, Google Summer of Code)
    * **AI & Machine Learning Challenges** (Kaggle, Hugging Face)
    * **Government Initiatives** (AICTE, MeitY, IndiaAI, MyGov)
    * **Internships & Fellowships**
    """,
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_origin_regex=r"^https:\/\/.*\.vercel\.app$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10 MB payload limit


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Enforce standard security headers on all HTTP responses."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    if settings.ENVIRONMENT == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


@app.middleware("http")
async def vercel_path_rewrite(request: Request, call_next):
    """
    Ensure requests rewritten by Vercel serverless functions are mapped back to their intended FastAPI route.
    """
    path = request.scope.get("path", "")
    if path in ("/api/index.py", "/api/index", "/api"):
        forwarded = request.headers.get("x-forwarded-uri") or request.headers.get("x-matched-path")
        if forwarded and not forwarded.startswith("/api/index"):
            request.scope["path"] = forwarded.split("?")[0]
        elif "__path" in request.query_params:
            request.scope["path"] = "/" + request.query_params["__path"].lstrip("/")
    return await call_next(request)


@app.middleware("http")
async def limit_request_size(request: Request, call_next):
    """Reject payloads exceeding maximum content size."""
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > MAX_CONTENT_LENGTH:
                return JSONResponse(
                    status_code=413,
                    content={"detail": "Request payload too large (max 10MB)"},
                )
        except ValueError:
            pass
    return await call_next(request)


# Register v1 API routers
api_v1 = FastAPI()
app.include_router(health_router, prefix=settings.API_V1_PREFIX)
app.include_router(auth_router, prefix=settings.API_V1_PREFIX)
app.include_router(opportunities_router, prefix=settings.API_V1_PREFIX)
app.include_router(events_router, prefix=settings.API_V1_PREFIX)
app.include_router(organizations_router, prefix=settings.API_V1_PREFIX)
app.include_router(sources_router, prefix=settings.API_V1_PREFIX)
app.include_router(ingestion_router, prefix=settings.API_V1_PREFIX)
app.include_router(discoveries_router, prefix=settings.API_V1_PREFIX)
app.include_router(program_watches_router, prefix=settings.API_V1_PREFIX)
app.include_router(dashboard_router, prefix=settings.API_V1_PREFIX)
app.include_router(audit_router, prefix=settings.API_V1_PREFIX)
app.include_router(users_router, prefix=settings.API_V1_PREFIX)
app.include_router(notifications_router, prefix=settings.API_V1_PREFIX)
app.include_router(verification_router, prefix=settings.API_V1_PREFIX)
app.include_router(scheduler_router, prefix=settings.API_V1_PREFIX)


from pathlib import Path
from fastapi.staticfiles import StaticFiles

# Optional Web SPA Mount (Phase 4)
web_dist = Path(__file__).resolve().parent.parent / "web" / "dist"
if (web_dist / "assets").exists():
    app.mount("/assets", StaticFiles(directory=str(web_dist / "assets")), name="web_assets")
if web_dist.exists():
    app.mount("/app", StaticFiles(directory=str(web_dist), html=True), name="web_app")


@app.get("/api/index.py", tags=["Root"])
@app.get("/api/index", tags=["Root"])
async def vercel_index_direct():
    return {
        "status": "healthy",
        "service": "SIGNAL Opportunity Intelligence Platform",
        "health": f"{settings.API_V1_PREFIX}/health",
        "docs": "/docs",
    }


@app.get("/", tags=["Root"])
async def root():
    """Root metadata endpoint or SPA entrypoint."""
    index_html = web_dist / "index.html"
    if index_html.exists():
        return FileResponse(str(index_html))
    return {
        "platform": settings.APP_NAME,
        "tagline": "Your Personal Opportunity Intelligence Network",
        "version": settings.APP_VERSION,
        "docs_url": "/docs",
        "api_v1_prefix": settings.API_V1_PREFIX,
    }


@app.exception_handler(404)
async def spa_404_handler(request: Request, exc):
    """Fallback non-API 404s to SPA index.html for client-side routing."""
    path = request.url.path
    if not (path.startswith("/api") or path.startswith("/docs") or path.startswith("/redoc") or path.startswith("/openapi")):
        index_html = web_dist / "index.html"
        if index_html.exists():
            return FileResponse(str(index_html))
    return JSONResponse(status_code=404, content={"detail": "Not Found"})


@app.get(f"{settings.API_V1_PREFIX}/ping", tags=["Health"])
async def ping():
    return {
        "status": "pong",
        "app": settings.APP_NAME,
        "is_serverless": is_serverless,
        "cwd": os.getcwd(),
    }


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    import traceback
    logger.error(f"Global unhandled exception on {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal Server Error", "error": str(exc), "traceback": traceback.format_exc()},
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("apps.api.main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG)
