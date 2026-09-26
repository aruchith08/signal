"""
Vercel Serverless Function entrypoint for SIGNAL FastAPI backend.
"""
import os
import sys

# Ensure repository root is on sys.path so modules (apps, services, shared, connectors) resolve cleanly
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(CURRENT_DIR)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# Signal Vercel serverless environment
os.environ.setdefault("VERCEL", "1")

# Default database for serverless ephemeral execution if not pointing to PostgreSQL
if "DATABASE_URL" not in os.environ or os.environ.get("DATABASE_URL", "").startswith("sqlite+aiosqlite:///."):
    os.environ["DATABASE_URL"] = "sqlite+aiosqlite:////tmp/signal_dev.db"

# Disable APScheduler in serverless lambda environment (invocations should be request-driven or Vercel Cron)
os.environ.setdefault("ENABLE_SCHEDULER", "false")

from apps.api.main import app

# Export as ASGI callable for Vercel Python runtime
handler = app
