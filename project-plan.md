Product Importer — Architecture & Implementation Plan

FastAPI • PostgreSQL • SQLAlchemy • Celery • Redis • Simple Frontend

This document defines the complete architecture, file structure, and development roadmap for building the Product Importer web application as required.

1. Overview

The application supports:

Uploading very large CSV files (~500,000 rows)

Asynchronous processing via Celery

Real-time progress updates on the UI

Full CRUD interface for Product management

Bulk delete

Webhook configuration + test

Clean, simple UI (React or minimal HTML/JS)

Deployment on Render / Railway / Heroku-compatible platform

This project is optimized for correctness, simplicity, and clarity — ideal for interview evaluation.

2. Technology Stack
Backend

FastAPI (Python)

Celery (background worker)

Redis (Celery broker + progress tracking)

PostgreSQL (primary DB)

SQLAlchemy + AsyncSession

Alembic (migrations)

Frontend

Choose either:

React (preferred, clearer UI)
OR

Plain HTML + JS with Fetch API (acceptable for assignment)

Deployment

Render / Railway / Fly.io / Heroku

Separate services for:

web (FastAPI)

worker (Celery)

redis

postgres

3. Core Functional Requirements
STORY 1 — CSV Upload

User must:

Upload CSV (up to 500k rows)

See progress updates (polling every 1s)

See success or error status

Backend must:

Accept CSV via multipart form upload

Save file to /tmp/uploads/{task_id}.csv

Create CELERY job:

Read CSV in streaming mode (no Pandas)

Process rows in batches (1,000 rows per batch)

Upsert products by SKU (case-insensitive)

Update Redis with progress:

{
  "status": "processing",
  "current": 15000,
  "total": 500000,
  "percent": 3.0
}

STORY 1A — Progress Visibility

Frontend polls endpoint:

GET /upload/status?task_id=...

returns:

{
  "task_id": "...",
  "state": "QUEUED | PROCESSING | COMPLETED | FAILED",
  "percent": 72,
  "message": "Processing batch 144 of 200"
}

4. Product Module Requirements

Endpoints:

GET /products

Pagination (offset-based is acceptable)

Filtering by SKU, name, active, description

POST /products

PUT /products/{id}

DELETE /products/{id}

DELETE /products/all (bulk delete)

Database Model: Product
id: int (PK)
sku: str (unique, case-insensitive)
name: str
description: str
price: float | null
active: bool (default true)
created_at: datetime
updated_at: datetime

Unique constraint:
CREATE UNIQUE INDEX idx_products_sku_lower
ON products (LOWER(sku));

5. Webhook Module Requirements
Endpoints:

GET /webhooks

POST /webhooks

PUT /webhooks/{id}

DELETE /webhooks/{id}

POST /webhooks/{id}/test

Model:
id: int
url: str
event_type: str
enabled: bool
last_status: int | null
last_response_time: float | null


Webhook triggers:

After CSV import completes

Uses Celery task deliver_webhook

Webhook test:

Simple POST request to the provided URL

Return status + time in UI

No need for HMAC signing (unless time permits).

6. Backend Architecture
/app
  /api
    upload_router.py
    product_router.py
    webhook_router.py
  /core
    config.py
    database.py
    celery_app.py
  /models
    product.py
    webhook.py
  /schemas
    product.py
    webhook.py
  /services
    csv_importer.py
    product_service.py
    webhook_service.py
    webhook_sender.py
  main.py

Key Components
CSV Import Logic

Use Python csv module

Stream file line by line

Group rows into batches of 1,000

Perform SQLAlchemy Core bulk upsert:

INSERT ... ON CONFLICT (lower(sku)) DO UPDATE ...

Celery Worker

import_products_task(task_id, file_path)

Uses Redis to update progress

Marks progress as:

QUEUED

PROCESSING

COMPLETED

FAILED

Progress Tracking

Redis keys:

upload:{task_id} = {
  status: "processing",
  current: n,
  total: n,
  percent: n
}

7. Frontend Architecture

If React:

/src
  /pages
    UploadPage.jsx
    ProductsPage.jsx
    WebhooksPage.jsx
  /components
    ProgressBar.jsx
    ProductTable.jsx
    ProductFormModal.jsx
    WebhookFormModal.jsx
  api.js


If HTML/JS:
Use minimal templates + fetch API calls.

Upload UI

File input

Upload button

Progress bar

Status messages

Retry button

Products UI

Table (paginated)

Filters (SKU, active, name)

CRUD modals

Bulk delete button

Webhooks UI

Table of webhooks

Create/update modal

Test button

Status display

8. Deployment Plan
Using Render (recommended):

Service: FastAPI backend

Worker: Celery worker

Database: Render PostgreSQL

Redis: Render Redis

Static site: React build

Environment vars:

DATABASE_URL=
REDIS_URL=
CELERY_BROKER_URL=
CELERY_RESULT_BACKEND=
SECRET_KEY=

Using Heroku:

One web dyno

One worker dyno

Heroku Postgres

Heroku Redis

Procfile:

web: gunicorn -k uvicorn.workers.UvicornWorker app.main:app
worker: celery -A app.core.celery_app worker --loglevel=info

9. Development Roadmap
Phase 1 — Core Backend Setup

FastAPI project

DB connection + Alembic

Models + Migrations

Basic product CRUD

Upload endpoint (store temp file)

Phase 2 — Celery Integration

Configure Celery + Redis

Implement import_products_task

Implement progress storage in Redis

Add /upload/status endpoint

Phase 3 — UI Implementation

Upload page + polling progress bar

Product CRUD UI

Bulk delete

Webhook CRUD + test button

Phase 4 — Final Testing

Import large sample (500k rows)

Verify progress accuracy

Test CRUD & pagination

Validate webhook test feature

Phase 5 — Deployment

Push to GitHub

Deploy backend + worker + redis + postgres

Deploy frontend

Provide public URLs