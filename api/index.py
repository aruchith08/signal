"""
Vercel Serverless Function entrypoint for SIGNAL FastAPI backend.
"""
import os
import sys
import traceback
from contextlib import asynccontextmanager
from pathlib import Path

# Ensure repository root and current directories are on sys.path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(CURRENT_DIR)
for p in [ROOT_DIR, CURRENT_DIR, os.path.join(ROOT_DIR, "apps"), os.getcwd(), "/var/task"]:
    if p and p not in sys.path:
        sys.path.insert(0, p)

# Signal Vercel serverless environment
os.environ["VERCEL"] = "1"
os.environ.setdefault("ENABLE_SCHEDULER", "false")

# Default database for serverless ephemeral execution if not pointing to PostgreSQL
if "DATABASE_URL" not in os.environ or "signal_dev.db" in os.environ.get("DATABASE_URL", ""):
    if not os.environ.get("DATABASE_URL", "").startswith("postgresql"):
        os.environ["DATABASE_URL"] = "sqlite+aiosqlite:////tmp/signal_dev.db"

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

# Attempt to load main application
_startup_error = None
main_app = None

try:
    from apps.api.main import app as main_app
except Exception:
    _startup_error = traceback.format_exc()


@asynccontextmanager
async def gateway_lifespan(app: FastAPI):
    """Run main app lifespan hooks if available."""
    if main_app and hasattr(main_app, "router") and main_app.router.lifespan_context:
        try:
            async with main_app.router.lifespan_context(main_app):
                yield
        except Exception as exc:
            import logging
            logging.getLogger("signal").error(f"Lifespan error: {exc}")
            yield
    else:
        yield


# Top-level FastAPI application instance explicitly recognized by Vercel AST scanner
app = FastAPI(
    title="SIGNAL Vercel Gateway",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=gateway_lifespan,
)

# Mount static assets if dist exists
web_dist = Path(ROOT_DIR) / "apps" / "web" / "dist"
if (web_dist / "assets").exists():
    app.mount("/assets", StaticFiles(directory=str(web_dist / "assets")), name="web_assets")


class VercelPathRewriteMiddleware:
    """Pure ASGI middleware to rewrite scope path BEFORE routing occurs."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            path = scope.get("path", "")
            if path in ("/api/index.py", "/api/index", "/api"):
                import urllib.parse
                qs = scope.get("query_string", b"").decode("utf-8", errors="replace")
                params = urllib.parse.parse_qs(qs)
                if "__path" in params and params["__path"]:
                    scope["path"] = params["__path"][0]
                else:
                    headers = dict(scope.get("headers", []))
                    forwarded = (
                        headers.get(b"x-forwarded-uri")
                        or headers.get(b"x-matched-path")
                        or headers.get(b"x-invoke-path")
                    )
                    if forwarded:
                        forwarded_str = forwarded.decode("utf-8", errors="replace")
                        if not forwarded_str.startswith("/api/index"):
                            scope["path"] = forwarded_str.split("?")[0]
        await self.app(scope, receive, send)


app.add_middleware(VercelPathRewriteMiddleware)


@app.middleware("http")
async def startup_check_middleware(request: Request, call_next):
    """Catch any startup/import errors and return full diagnostics instead of opaque 500s."""
    if _startup_error:
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "phase": "STARTUP_IMPORT_FAILED",
                "message": "FastAPI application failed to import on Vercel.",
                "traceback": _startup_error,
                "sys_path": sys.path,
                "cwd": os.getcwd(),
            },
        )
    return await call_next(request)


# If main_app loaded cleanly, register its routers, middlewares, and exception handlers
if main_app is not None:
    app.include_router(main_app.router)
    for middleware in getattr(main_app, "user_middleware", []):
        app.user_middleware.append(middleware)
    for exc, handler in getattr(main_app, "exception_handlers", {}).items():
        app.add_exception_handler(exc, handler)


@app.get("/api/diagnostic", tags=["Diagnostic"])
@app.get("/api/v1/diagnostic", tags=["Diagnostic"])
async def diagnostic_check():
    """Diagnostic probe exposing serverless environment and database connectivity status."""
    from apps.api.config import settings
    from apps.api.database import is_serverless, db_url
    
    db_masked = db_url.split("@")[-1] if "@" in db_url else db_url
    return {
        "status": "ok",
        "app_name": settings.APP_NAME,
        "is_serverless": is_serverless,
        "environment": settings.ENVIRONMENT,
        "database_target": db_masked,
        "python_version": sys.version,
        "web_dist_exists": web_dist.exists(),
        "index_html_exists": (web_dist / "index.html").exists(),
    }


@app.get("/index.html", include_in_schema=False)
async def serve_index():
    index_file = web_dist / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return JSONResponse(content={"detail": "Index file not found in build output"}, status_code=404)


@app.get("/signal-icon.svg", include_in_schema=False)
async def serve_favicon():
    icon_file = web_dist / "signal-icon.svg"
    if icon_file.exists():
        return FileResponse(str(icon_file), media_type="image/svg+xml")
    public_icon = Path(ROOT_DIR) / "apps" / "web" / "public" / "signal-icon.svg"
    if public_icon.exists():
        return FileResponse(str(public_icon), media_type="image/svg+xml")
    return Response(status_code=204)


@app.post("/api/v1/init-db", tags=["Diagnostic"])
@app.get("/api/v1/init-db", tags=["Diagnostic"])
async def trigger_init_db():
    """Explicit endpoint to create database tables and seed sources on demand."""
    from apps.api.database import init_db, AsyncSessionLocal
    from services.sources.registry import ensure_devfolio_source, ensure_unstop_source, ensure_source
    
    results = {}
    try:
        await init_db()
        results["schema"] = "initialized"
    except Exception as exc:
        results["schema"] = f"error: {exc}"
        
    try:
        async with AsyncSessionLocal() as session:
            await ensure_unstop_source(session)
            await ensure_devfolio_source(session)
            for slug in ["codeforces", "sih", "gsoc", "atcoder", "github-blog", "kaggle", "huggingface"]:
                await ensure_source(slug, session)
            await session.commit()
        results["sources"] = "seeded"
    except Exception as exc:
        results["sources"] = f"error: {exc}"
        
    return {"status": "complete", "details": results}


# Secondary alias
handler = app
