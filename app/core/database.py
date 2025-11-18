from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from typing import AsyncGenerator

from .config import settings

# ---------------------------------------------------------------------------
# Sync SQLAlchemy setup
# ---------------------------------------------------------------------------
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if settings.database_url.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI dependency that yields a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ---------------------------------------------------------------------------
# Async SQLAlchemy setup
# ---------------------------------------------------------------------------
# Convert sync DATABASE_URL to an async-compatible driver if required.  This is
# a *best-effort* helper that covers the common cases used in this project.
_async_url = settings.database_url
if _async_url.startswith("postgresql://") and "+asyncpg" not in _async_url:
    _async_url = _async_url.replace("postgresql://", "postgresql+asyncpg://", 1)
elif _async_url.startswith("sqlite:///") and "+aiosqlite" not in _async_url:
    _async_url = _async_url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)

async_engine = create_async_engine(_async_url, echo=False, future=True)
AsyncSessionLocal = async_sessionmaker(async_engine, expire_on_commit=False, class_=AsyncSession)


async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an **async** database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
