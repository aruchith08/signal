"""
Database setup and session management using SQLAlchemy 2.0 Async
"""
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

from apps.api.config import settings

import os
from sqlalchemy import event

# Normalize database URL
db_url = settings.DATABASE_URL
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql+asyncpg://", 1)
elif db_url.startswith("postgresql://") and not db_url.startswith("postgresql+asyncpg://"):
    db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

# In Vercel serverless environment, use /tmp for default SQLite persistence
if os.getenv("VERCEL") and db_url.startswith("sqlite+aiosqlite:///."):
    db_url = "sqlite+aiosqlite:////tmp/signal_dev.db"

# Create async engine
connect_args = {}
if db_url.startswith("sqlite"):
    connect_args["check_same_thread"] = False
    connect_args["timeout"] = 30

engine = create_async_engine(
    db_url,
    echo=settings.DATABASE_ECHO,
    future=True,
    connect_args=connect_args,
)

if db_url.startswith("sqlite"):
    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
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
    async with engine.begin() as conn:
        # Import models so they are registered with Base metadata
        import apps.api.models  # noqa: F401
        await conn.run_sync(Base.metadata.create_all)
