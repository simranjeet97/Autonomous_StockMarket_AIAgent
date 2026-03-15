"""
core/database.py
────────────────
SQLAlchemy async engine and session management for SQLite.
"""

import logging
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from core.config import settings

logger = logging.getLogger(__name__)

# Create async engine for SQLite
engine = create_async_engine(
    settings.db_url,
    connect_args={"check_same_thread": False},  # Required for SQLite + Async
)

# Session factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for providing a database session."""
    async with AsyncSessionLocal() as session:
        yield session


async def init_db():
    """Create tables if they don't exist."""
    from core.models import Base as _  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables initialised.")
