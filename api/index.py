"""
Vercel Serverless Function entrypoint for SIGNAL FastAPI backend.
"""
import os
import sys

# Ensure repository root and current directories are on sys.path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(CURRENT_DIR)
for p in [ROOT_DIR, CURRENT_DIR, os.getcwd()]:
    if p and p not in sys.path:
        sys.path.insert(0, p)

# Signal Vercel serverless environment
os.environ["VERCEL"] = "1"
os.environ.setdefault("ENABLE_SCHEDULER", "false")

# Default database for serverless ephemeral execution if not pointing to PostgreSQL
if "DATABASE_URL" not in os.environ or "signal_dev.db" in os.environ.get("DATABASE_URL", ""):
    if not os.environ.get("DATABASE_URL", "").startswith("postgresql"):
        os.environ["DATABASE_URL"] = "sqlite+aiosqlite:////tmp/signal_dev.db"

# Top-level FastAPI application export recognized by Vercel AST scanner
try:
    from apps.api.main import app
    handler = app
except Exception as exc:
    import traceback
    err_tb = traceback.format_exc()
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse
    app = FastAPI(title="SIGNAL Fallback Error Handler")
    @app.api_route("/{full_path:path}", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD"])
    async def report_startup_error(full_path: str = ""):
        return JSONResponse(
            status_code=500,
            content={
                "error": "FastAPI App Import Failed on Vercel",
                "message": str(exc),
                "traceback": err_tb,
                "sys_path": sys.path,
                "cwd": os.getcwd(),
            }
        )
    handler = app
