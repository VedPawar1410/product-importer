#!/usr/bin/env bash
set -e

# Run migrations if Alembic is present
if [ -f "./alembic.ini" ]; then
  alembic upgrade head
fi

exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers "${UVICORN_WORKERS:-4}"
