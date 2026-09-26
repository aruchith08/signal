"""
Vercel Serverless Function entrypoint for SIGNAL FastAPI backend.
"""
import os
import sys
import logging
import traceback

# Ensure repository root is on sys.path so modules (apps, services, shared, connectors) resolve cleanly
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(CURRENT_DIR)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# Signal Vercel serverless environment
os.environ["VERCEL"] = "1"
os.environ.setdefault("ENABLE_SCHEDULER", "false")

# Default database for serverless ephemeral execution if not pointing to PostgreSQL
if "DATABASE_URL" not in os.environ or "signal_dev.db" in os.environ.get("DATABASE_URL", ""):
    if not os.environ.get("DATABASE_URL", "").startswith("postgresql"):
        os.environ["DATABASE_URL"] = "sqlite+aiosqlite:////tmp/signal_dev.db"

try:
    from apps.api.main import app
    handler = app
except Exception as e:
    err_trace = traceback.format_exc()
    logging.error(f"Fatal error initializing SIGNAL on Vercel: {e}\n{err_trace}")
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse

    app = FastAPI(title="SIGNAL - Startup Error")

    @app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD", "PATCH"])
    async def debug_error(path: str):
        return JSONResponse(
            status_code=500,
            content={
                "error": "SIGNAL FastAPI Startup Failed on Vercel",
                "message": str(e),
                "traceback": err_trace,
            },
        )
    handler = app
