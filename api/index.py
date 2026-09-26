"""
Vercel Serverless Function entrypoint for SIGNAL FastAPI backend.
"""
import os
import sys

# Ensure repository root and current directories are on sys.path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(CURRENT_DIR)
for p in [ROOT_DIR, CURRENT_DIR, os.getcwd(), "/var/task"]:
    if p and p not in sys.path:
        sys.path.insert(0, p)

# Signal Vercel serverless environment
os.environ["VERCEL"] = "1"
os.environ.setdefault("ENABLE_SCHEDULER", "false")

# Default database for serverless ephemeral execution if not pointing to PostgreSQL
if "DATABASE_URL" not in os.environ or "signal_dev.db" in os.environ.get("DATABASE_URL", ""):
    if not os.environ.get("DATABASE_URL", "").startswith("postgresql"):
        os.environ["DATABASE_URL"] = "sqlite+aiosqlite:////tmp/signal_dev.db"

from fastapi import FastAPI
from apps.api.main import app as main_app

# Top-level FastAPI application instance explicitly recognized by Vercel AST scanner
app = FastAPI(title="SIGNAL Vercel Gateway", docs_url=None, redoc_url=None, openapi_url=None)
app.mount("/", main_app)

# Secondary alias
handler = app
