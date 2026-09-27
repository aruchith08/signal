"""
Database setup and session management using SQLAlchemy 2.0 Async
"""
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

from apps.api.config import settings

import os
from sqlalchemy import event

def check_is_serverless() -> bool:
    if os.getenv("VERCEL") or os.getenv("VERCEL_ENV") or os.getenv("AWS_LAMBDA_FUNCTION_NAME") or os.getenv("LAMBDA_TASK_ROOT"):
        return True
    cwd = os.path.abspath(".").lower()
    if "vercel" in cwd or "/var/task" in cwd or "\\var\\task" in cwd:
        return True
    try:
        test_path = os.path.join(".", ".probe_rw")
        with open(test_path, "w") as f:
            f.write("1")
        os.remove(test_path)
        return False
    except Exception:
        return True

is_serverless = check_is_serverless()

# Normalize database URL
db_url = settings.DATABASE_URL
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql+asyncpg://", 1)
elif db_url.startswith("postgresql://") and not db_url.startswith("postgresql+asyncpg://"):
    db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

import tempfile

# In serverless environments (e.g. Vercel / AWS Lambda), the filesystem is read-only except tempdir
if is_serverless and ("sqlite" in db_url):
    temp_dir = tempfile.gettempdir().replace("\\", "/").rstrip("/")
    db_url = f"sqlite+aiosqlite:///{temp_dir}/signal_dev.db"

# Create async engine
connect_args = {}
engine_kwargs = {"echo": settings.DATABASE_ECHO, "future": True}

if db_url.startswith("sqlite"):
    connect_args["check_same_thread"] = False
    connect_args["timeout"] = 30
else:
    # Supabase / PgBouncer transaction mode pooler (port 6543) requires statement_cache_size=0
    connect_args["statement_cache_size"] = 0
    if "localhost" not in db_url and "127.0.0.1" not in db_url:
        connect_args["ssl"] = "require"
    if is_serverless:
        from sqlalchemy.pool import NullPool
        engine_kwargs["poolclass"] = NullPool

engine_kwargs["connect_args"] = connect_args
engine = create_async_engine(db_url, **engine_kwargs)

if db_url.startswith("sqlite"):
    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        if not is_serverless:
            cursor.execute("PRAGMA journal_mode=WAL")
        else:
            cursor.execute("PRAGMA journal_mode=MEMORY")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.close()


# Async session factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

Base = declarative_base()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for obtaining an async database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Create all tables in the database (useful for dev and testing)."""
    try:
        async with engine.begin() as conn:
            # Import models so they are registered with Base metadata
            import apps.api.models  # noqa: F401
            await conn.run_sync(Base.metadata.create_all)
            if engine.dialect.name == "postgresql":
                from sqlalchemy import text
                for stmt in [
                    "ALTER TABLE opportunities ALTER COLUMN last_verified_at TYPE TIMESTAMP WITH TIME ZONE;",
                    "ALTER TABLE semantic_match_candidates ALTER COLUMN resolved_at TYPE TIMESTAMP WITH TIME ZONE;",
                    "ALTER TABLE verification_reviews ALTER COLUMN resolved_at TYPE TIMESTAMP WITH TIME ZONE;",
                ]:
                    try:
                        await conn.execute(text(stmt))
                    except Exception:
                        pass
    except Exception as exc:
        import logging
        logging.getLogger("signal").error(f"init_db caught schema creation error: {exc}")

