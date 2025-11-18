#!/usr/bin/env bash
set -e

echo "Starting Product Importer (Web + Worker in single container for Render free tier)"

# Start Celery worker in background
echo "Starting Celery worker..."
celery -A app.core.celery_app.celery_app worker \
  --loglevel="${CELERY_LOG_LEVEL:-info}" \
  --concurrency="${CELERY_CONCURRENCY:-2}" &

# Store the background process PID
CELERY_PID=$!
echo "Celery worker started with PID: $CELERY_PID"

# Function to handle shutdown gracefully
cleanup() {
    echo "Shutting down..."
    echo "Stopping Celery worker (PID: $CELERY_PID)..."
    kill -TERM $CELERY_PID 2>/dev/null || true
    wait $CELERY_PID 2>/dev/null || true
    echo "Cleanup complete"
    exit 0
}

# Trap SIGTERM and SIGINT for graceful shutdown
trap cleanup SIGTERM SIGINT

# Wait a moment for Celery to initialize
sleep 3

# Start Uvicorn web server in foreground
echo "Starting Uvicorn web server..."
exec uvicorn app.main:app \
  --host 0.0.0.0 \
  --port "${PORT:-8000}" \
  --workers "${UVICORN_WORKERS:-1}"

