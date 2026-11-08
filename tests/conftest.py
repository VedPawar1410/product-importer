"""Shared test setup: real Postgres + Redis, with Celery tasks run inline.

Defaults match `docker compose up -d db redis`; override them with
TEST_DATABASE_URL / TEST_REDIS_URL. A separate database (products_test) and
Redis db (15) are used so dev data is never touched. If either service is
unreachable, every test is skipped with a hint.
"""

import os
import tempfile

import pytest

TEST_DB = os.getenv("TEST_DATABASE_URL", "postgresql://postgres:postgres@localhost:5433/products_test")
TEST_REDIS = os.getenv("TEST_REDIS_URL", "redis://localhost:6379/15")

# The app reads its settings when it's first imported, so point it at the test
# services before any test imports `app`.
os.environ.update(
    DATABASE_URL=TEST_DB,
    CELERY_BROKER_URL=TEST_REDIS,
    CELERY_RESULT_BACKEND=TEST_REDIS,
    UPLOAD_DIR=tempfile.mkdtemp(prefix="product-importer-uploads-"),
)


def _prepare_services() -> str | None:
    """Create the test database if needed and ping Redis. Returns an error message or None."""
    import psycopg2
    import redis
    from sqlalchemy.engine import make_url

    url = make_url(TEST_DB)
    try:
        admin = psycopg2.connect(
            host=url.host, port=url.port or 5432, user=url.username,
            password=url.password, dbname="postgres", connect_timeout=3,
        )
        admin.autocommit = True  # CREATE DATABASE can't run inside a transaction
        with admin.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (url.database,))
            if cur.fetchone() is None:
                cur.execute(f'CREATE DATABASE "{url.database}"')
        admin.close()
        redis.Redis.from_url(TEST_REDIS, socket_connect_timeout=3).ping()
    except Exception as exc:  # noqa: BLE001
        return str(exc).strip()
    return None


@pytest.fixture(scope="session")
def client():
    error = _prepare_services()
    if error:
        pytest.skip(f"Postgres/Redis not reachable ({error}). Start them: docker compose up -d db redis")

    from fastapi.testclient import TestClient

    from app.core.celery_app import celery_app
    from app.main import app

    # Run Celery tasks synchronously inside .delay(), so one request exercises
    # upload -> import task -> database -> webhook without a worker process.
    celery_app.conf.update(task_always_eager=True, task_eager_propagates=True)

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def clean_tables(client):
    """Every test starts with empty tables."""
    from sqlalchemy import text

    from app.core.database import engine

    with engine.begin() as conn:
        conn.execute(text("TRUNCATE products, webhooks, webhook_deliveries RESTART IDENTITY"))
