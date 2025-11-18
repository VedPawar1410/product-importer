#!/usr/bin/env bash
set -e

exec celery -A app.core.celery_app.celery_app worker --loglevel "${CELERY_LOG_LEVEL:-info}" --concurrency "${CELERY_CONCURRENCY:-4}"
