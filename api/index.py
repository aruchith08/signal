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
os.environ["VERCEL"] = "1"
os.environ.setdefault("ENABLE_SCHEDULER", "false")

# Default database for serverless ephemeral execution if not pointing to PostgreSQL
if "DATABASE_URL" not in os.environ or "signal_dev.db" in os.environ.get("DATABASE_URL", ""):
    if not os.environ.get("DATABASE_URL", "").startswith("postgresql"):
        os.environ["DATABASE_URL"] = "sqlite+aiosqlite:////tmp/signal_dev.db"

# Top-level FastAPI application export recognized by Vercel AST scanner
from apps.api.main import app

# Secondary alias
handler = app
