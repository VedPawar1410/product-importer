from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from typing import AsyncGenerator

from .config import settings

# pool_pre_ping: hosted Postgres (e.g. Neon) suspends when idle and drops open
# connections. Pinging before reuse swaps a dead pooled connection for a fresh one
# instead of failing the first request after a quiet period.

# ---------------------------------------------------------------------------
# Sync SQLAlchemy setup (psycopg2) – used by the Celery worker and webhook routes
# ---------------------------------------------------------------------------
engine = create_engine(settings.database_url, pool_pre_ping=True)
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
# Async SQLAlchemy setup (asyncpg) – used by the product routes
# ---------------------------------------------------------------------------
def _async_engine_args(database_url: str):
    """Turn a libpq-style URL into an asyncpg URL plus connect_args.

    Providers like Neon append `?sslmode=require&channel_binding=require`.
    psycopg2 (libpq) understands those, but asyncpg rejects them
    ("unexpected keyword argument 'sslmode'"), so they're removed from the URL
    and the SSL mode is passed the way asyncpg expects.
    """
    url = make_url(database_url).set(drivername="postgresql+asyncpg")
    query = dict(url.query)
    sslmode = query.pop("sslmode", None)
    query.pop("channel_binding", None)
    connect_args = {"ssl": sslmode} if sslmode and sslmode != "disable" else {}
    return url.set(query=query), connect_args


_async_url, _async_connect_args = _async_engine_args(settings.database_url)
async_engine = create_async_engine(_async_url, connect_args=_async_connect_args, pool_pre_ping=True)
AsyncSessionLocal = async_sessionmaker(async_engine, expire_on_commit=False, class_=AsyncSession)


async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an **async** database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
