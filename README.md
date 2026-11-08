# Product Importer

Upload a product CSV of up to 500,000 rows, watch it import live, then browse, edit and bulk-delete the catalog and get a webhook when an import finishes.

**Live demo:** https://product-importer-web-e3bi.onrender.com (free tier, so the first visit can take ~50 s while the server wakes up)

| Headline | Result |
|---|---|
| 500,000-row CSV (50.8 MB) on the live free tier | **imported in 442 s, 0 failed** |
| Same file locally | 29.5 s |
| Redis peak memory during that import | **1.6 MB** (was 52 MB, more than double the 25 MB free limit) |
| Automated tests | 11 passing (real Postgres + Redis) |
| Live API checks after deploy | 10 / 10 |

Originally a take-home assignment (built 18–19 Nov 2025), revived and fixed in Nov 2026. The [learning log](#learning-log-mistakes-and-what-i-learned) records what went wrong and why.

---

## How it works

```
 Browser                FastAPI (web)                  Redis                 Celery worker              Postgres (Neon)
 ───────                ─────────────                  ─────                 ─────────────              ───────────────
 drop CSV ──POST──▶  stream file to /tmp/uploads ──▶  job: (task_id, path) ──▶ read CSV row by row
                     (1 MB chunks)                                            validate → batch of 1,000
                                                                              INSERT … ON CONFLICT
                                                                              (lower(sku)) DO UPDATE ──────▶ products
 progress ring ◀─GET /upload/status─ reads ◀──── upload:{id}:progress ◀── writes after every batch
                                                                              on finish: POST to every
                                                                              "import.completed" webhook
```

Web and worker run in **one container** on Render (free plan has no worker service), so they share `/tmp`.

**Why these choices**

- **Celery + Redis for the import:** a 500k-row file takes minutes; doing it inside the HTTP request would time out and block the server. The request returns a `task_id` in ~0.3 s and the browser polls progress.
- **The file goes to disk, not through Redis:** a queue should carry messages, not payloads. Storing the whole CSV in Redis capped uploads at Redis's RAM (25 MB on the free tier). Now Redis only holds the job and a tiny progress hash.
- **Batches of 1,000 with a Postgres upsert:** one round-trip per 1,000 rows instead of per row, and `ON CONFLICT (lower(sku)) DO UPDATE` makes re-importing a SKU update the product.
- **A unique index on `lower(sku)`:** "SKUs are unique ignoring case" is enforced by the database, so it holds across batches, uploads and the API, not just inside one batch.
- **Streaming everywhere:** the upload is copied in chunks and the worker reads one row at a time, so memory stays flat whatever the file size.
- **Plain HTML/CSS/JS frontend:** three pages, no build step, so deployment is just the Python image.

## Data

There's no real dataset; the importer works on any CSV in this shape:

| column | required | notes |
|---|---|---|
| `sku` | yes | unique, case-insensitive (`ABC-1` = `abc-1`) |
| `name` | yes | |
| `description` | no | |
| `price` | no | number |
| `active` | no | `true` / `false`, default `true` |

- [`frontend/sample-products.csv`](frontend/sample-products.csv): 200 realistic products (6 categories, 15 inactive, a few without a price). Downloadable from the Import page; it's what the live demo shows.
- **500k load-test file:** synthetic, regenerated on demand (not committed):
  ```bash
  python scripts/generate_csv.py            # → data/products-500k.csv, 50.8 MB
  ```
  It's deterministic, so it reproduces the exact file used for the numbers above.
- Re-importing an existing SKU updates it; if a file repeats a SKU, the last row wins. Invalid rows (no SKU or name, a price like `abc`) are skipped and reported as `failed_rows`.

## Results

**Before vs. after the revive**

| | Before (code as found, Nov 2026) | After |
|---|---|---|
| Live site | Down: its free Render Postgres had been deleted and the app crashed on startup | Up (Render + Neon) |
| Fresh build | Crashed: unpinned SQLAlchemy 2.1 / billiard 4.3 | 49 packages locked, reproducible |
| Products & Webhooks pages | "Failed to load" (404) on every visit | Work |
| API probe (18 checks) | 12 / 18 | 16 / 18 (the 2 left are an unbuilt feature, see Limitations) |
| SKU `abc` vs `ABC` | Two separate products | One product |
| Webhook after import | Never sent | Sent |
| Invalid rows | Silently dropped, reported as 0 failed | Counted and shown |
| Bulk delete | 422 error | Works, respects filters |
| 500k rows on the free tier | Impossible (52 MB in Redis vs 25 MB limit) | 442 s |
| Automated tests | 0 | 11 |

**500,000-row import (50.8 MB)**

| Where | Upload request | Upload → done | Rows imported / failed |
|---|---|---|---|
| Local (M-series Mac, local Postgres) | 0.3 s | 29.5 s | 500,000 / 0 |
| Live (Render free + Neon free) | 21 s (my upload bandwidth) | 442 s | 500,000 / 0 |

Local peaks during the import: web process 137 MB, largest Celery process 108 MB, Redis 1.6 MB.

## Project structure

```
product-importer/
├── app/
│   ├── main.py                  # FastAPI app: routers, /health, serves frontend/ at /
│   ├── api/
│   │   ├── upload_router.py     # POST /upload/start (stream to disk, enqueue), GET /upload/status/{id}
│   │   ├── product_router.py    # /products CRUD, filters, pagination, DELETE /products/all
│   │   └── webhook_router.py    # /webhooks create/list/delete, POST /webhooks/test/{event}
│   ├── core/
│   │   ├── config.py            # settings from env vars (DATABASE_URL, CELERY_*, UPLOAD_DIR)
│   │   ├── database.py          # sync (psycopg2) + async (asyncpg) engines, Neon SSL handling
│   │   └── celery_app.py        # Celery app + import_products task
│   ├── models/                  # SQLAlchemy models (Product with lower(sku) unique index, Webhook)
│   ├── schemas/                 # Pydantic request/response models
│   └── services/
│       ├── csv_importer.py      # stream + validate + batch + progress
│       ├── product_service.py   # batch upsert (ON CONFLICT lower(sku))
│       └── webhook_service.py   # webhook CRUD + delivery task
├── frontend/                    # index (import), products, webhooks pages; app.js; styles.css; sample CSV
├── tests/                       # pytest: conftest.py (real Postgres/Redis, eager Celery), test_api.py
├── scripts/generate_csv.py      # synthetic load-test CSV generator
├── planning/project-plan.md     # the original assignment plan
├── Dockerfile                   # image used on Render (web + worker via run_web_with_worker.sh)
├── Dockerfile.worker            # worker image for local docker compose
├── docker-compose.yml           # local stack: web, worker, postgres, redis
├── render.yaml                  # Render Blueprint (web service + Redis)
├── run_web.sh / run_worker.sh / run_web_with_worker.sh
├── requirements.in              # direct dependencies (edit this)
├── requirements.txt             # full lockfile generated from requirements.in
├── requirements-dev.txt         # + pytest, httpx
├── pytest.ini, .python-version (3.11), .env.example, .dockerignore
```

## Run locally

**With Docker** (web, worker, Postgres and Redis together):

```bash
docker compose up --build
```

Open http://localhost:8000. *(Not re-verified during the revive: Docker isn't installed on the machine I used. Everything below was.)*

**Without Docker** (needs Python 3.11, a local Postgres and Redis):

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env        # point DATABASE_URL / CELERY_* at your Postgres and Redis
```

```bash
celery -A app.core.celery_app.celery_app worker --loglevel=info --concurrency=2
```

```bash
uvicorn app.main:app --port 8000
```

Use a UTF-8 database (`createdb -E UTF8 ...`). A `SQL_ASCII` cluster rejects names with characters like "–".

## Tests

```bash
docker compose up -d db redis
```

```bash
pytest
```

The tests create their own `products_test` database and use Redis db 15, so dev data is untouched. Celery runs in eager mode, so each upload test goes through the real path (HTTP → task → Postgres → webhook) without a worker. If Postgres or Redis isn't reachable, the tests are skipped with a hint. Point them elsewhere with `TEST_DATABASE_URL` / `TEST_REDIS_URL`.

## Deployment

- **Render** (Blueprint from `render.yaml`): one free Docker web service running uvicorn + a Celery worker (`run_web_with_worker.sh`), plus free Render Key Value (Redis). Health check: `/health`.
- **Postgres on Neon** (free tier; pick the region closest to Render's Oregon): Render's free Postgres is deleted 30 days after creation, which is what killed this app the first time. Neon's free tier doesn't expire.
- Environment variables on the web service:
  - `DATABASE_URL`: Neon connection string, **direct (not pooled)**, so asyncpg's prepared statements work. Set in the dashboard, never committed.
  - `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`: wired to the Render Redis by `render.yaml`.
  - `CELERY_CONCURRENCY=1`, `UVICORN_WORKERS=1`: keep the shared container inside 512 MB.
- Python 3.11 (`python:3.11-slim`); dependencies from the locked `requirements.txt`.
- Auto-deploy on push to `main`.

## Limitations

- **Cold starts:** the free instance sleeps after 15 minutes idle; the first request takes ~50 s (the UI shows a "waking up" note).
- **Web and worker must share a disk:** uploads wait in `/tmp`. Splitting them into separate services would need object storage (e.g. S3) instead.
- **The live free tier is slow for big files:** 500k rows took ~7.5 min (network round-trips to Neon on every batch, one worker process). Fine for a demo, not for production volumes.
- **Webhooks are basic:** no update endpoint (the UI edits by create-then-delete), no delivery status or retries, no signing. The original plan's "last status / response time" is not built.
- **SKU filter is exact** (case-insensitive); name search is a substring match.
- **No migrations:** tables are created with `create_all()`, which never alters existing tables; schema changes on a live database would need Alembic.
- **No auth:** anyone with the URL can import or delete. It's a demo.
- **Neon's free tier has a small storage cap:** 500k rows fit comfortably, but it isn't sized for production catalogs.

## Learning log: mistakes and what I learned

Built in layers. Each layer records what went wrong and the lesson.

### Layer 1 - The build (18 Nov 2025, FastAPI + Celery + Redis + Postgres, Docker Compose)

*What I built:* a take-home product importer in about a day: async CSV import with progress, product CRUD, webhooks, and a plain HTML/JS frontend.

| # | Mistake | What actually happened | Lesson |
|---|---|---|---|
| 1.1 | **Static files mounted at `/` shadowed the API** | Routes were `/products/` and `/webhooks/`; the frontend called `/products`. The catch-all `StaticFiles` mount matched first and returned 404, so the Products and Webhooks pages showed "Failed to load" from the day they were written. My API tests used the slashed paths and passed. | Test through the real client, not only the API. A catch-all mount changes routing for everything else. |
| 1.2 | **"Unique ignoring case" enforced in Python only** | `unique=True` on `sku` is case-sensitive; dedup ran only inside each 1,000-row batch. `CASE-abc` then `CASE-ABC` became two products; the API accepted `crud1` next to `CRUD1`. | Put invariants in the database: a functional unique index on `lower(sku)`, and make the upsert target the same expression. |
| 1.3 | **`suppress(Exception)` hid a broken feature** | After every import the task built `WebhookCreate(url="import.completed")`, missing the required `event`, so it raised and was silently swallowed. No webhook was ever sent. | Never swallow exceptions around business logic; a missing feature should fail loudly in tests. |
| 1.4 | **Invalid rows silently dropped** | Bad rows were skipped with `continue` and progress hard-coded `failed_rows: 0`. A file with 2 bad rows of 3 reported 0 failures. | Count and surface every skipped row. "Never silently drop data" is a requirement, not a nicety. |
| 1.5 | **Route order bug** | `DELETE /products/{product_id}` was declared before `DELETE /products/all`, so "all" was parsed as an id → 422. Bulk delete never worked. | FastAPI matches routes in declaration order; put fixed paths before parameterised ones. |
| 1.6 | **Paging without `ORDER BY`** | `SELECT … OFFSET … LIMIT` with no order: Postgres may return rows in any order, so pages can repeat or skip rows. | OFFSET pagination needs a stable sort, ideally on an indexed column. |
| 1.7 | **Unpinned dependencies** | `requirements.txt` said `sqlalchemy>=2.0`, `celery`, … A year later a fresh build pulled SQLAlchemy 2.1 (no greenlet, new default driver) and billiard 4.3 (crashes Celery 5.5's worker pool). | Lock the whole dependency tree, not just top-level packages. |
| 1.8 | **Leftover scaffolding** | A duplicate `ProductCreate` class (the second silently replaced the first), an empty `webhook_sender.py` stub, a placeholder `example_task`, Alembic installed but never used. | Delete scaffolding as you go; dead code misleads the next reader (me, a year later). |

### Layer 2 - The Render free-tier fight (18–19 Nov 2025, Render Blueprint)

*What I built:* a Render deployment, bending the design to free-tier limits (no disks, no worker services).

| # | Mistake | What actually happened | Lesson |
|---|---|---|---|
| 2.1 | **Pushed the whole CSV through Redis** | With no shared disk between services, I stored uploads in Redis. A 500k-row file is 50.8 MB and peaked Redis at 52 MB, versus 25 MB on the free plan. I "fixed" it with a 5 MB upload cap, which defeated the 500k-row requirement. | Queues carry messages, not payloads. Once web and worker shared a container, plain `/tmp` was enough. |
| 2.2 | **Depended on an expiring database** | `render.yaml` created a free Render Postgres, which is deleted 30 days after creation. It vanished around Dec 2025; the app ran `create_all()` at import time, crashed before binding a port, and Render marked it "Failed". | Read the free tier's expiry rules; keep stateful services on something that doesn't expire. |
| 2.3 | **Debug endpoints in production** | `/debug/config` publicly returned the first 20 characters of the database URL. | Debug routes are a leak waiting to happen; use logs, and remove them once the bug is found. |
| 2.4 | **Committed `.env`, no `.dockerignore`** | `.env` was tracked despite being in `.gitignore` (added before the ignore rule), and `COPY . /code` baked it, `.git` and sample CSVs into the image. | Add `.gitignore` and `.dockerignore` first; `git rm --cached` anything tracked by mistake. |
| 2.5 | **Lost track of what was deployed** | Auto-deploy was off: Render ran `be1e81a` the whole time, and the 7 commits after it never ran (4 code changes, 2 of which were never even pushed, plus 3 README edits). README edits made on GitHub's website were never pulled, so local and remote history diverged. | Know which commit is live. Pull before you push; turn on auto-deploy or deploy deliberately. |

### Layer 3 - The rebuild (Nov 2026)

*What I did:* audited the year-old project, fixed root causes one commit at a time, redeployed it on Render + Neon, and redesigned the frontend.

| # | Decision | Why |
|---|---|---|
| 3.1 | Lock all 49 packages with `uv pip compile` (`requirements.in` → `requirements.txt`), with an explicit `billiard<4.3` | Reproducible builds; top-level pins alone still broke the worker (fixes 1.7) |
| 3.2 | Functional unique index on `lower(sku)` + `ON CONFLICT (lower(sku))`, 409 on API duplicates | Case-insensitive uniqueness everywhere (fixes 1.2) |
| 3.3 | Dispatch `import.completed` via the existing webhook task; count and show failed rows | Features that silently didn't work (fixes 1.3, 1.4) |
| 3.4 | Fixed route order, no-slash collection routes, `ORDER BY id DESC` | Bulk delete, the UI pages and stable paging (fixes 1.1, 1.5, 1.6) |
| 3.5 | Stream uploads to a shared upload directory; Redis keys expire after 24 h | Removes the 25 MB ceiling; Redis peak 52 MB → 1.6 MB (fixes 2.1) |
| 3.6 | Postgres on Neon; asyncpg gets `sslmode` translated to `ssl`; `pool_pre_ping` | Database that doesn't expire; Neon's URL params crashed asyncpg; Neon drops idle connections (fixes 2.2) |
| 3.7 | 11 integration tests on real Postgres + Redis with eager Celery | The bugs lived in Postgres features and wiring, which mocks wouldn't catch |
| 3.8 | Removed `.env` from git, debug routes, stubs and stale deploy docs; added `.dockerignore` | Fixes 1.8, 2.3, 2.4 |
| 3.9 | Redesigned the frontend in plain HTML/CSS/JS: live progress ring, debounced search, modals, toasts, dark mode | Presentable without adding a build step or new dependencies |

*Known gaps I chose not to fix:* webhook update/delivery status/retries, auth, Alembic migrations, separate web/worker services.

### Key takeaways

1. **Test through the real client.** Two of the worst bugs (pages 404ing, bulk delete) were invisible to API-level tests.
2. **Enforce invariants in the database.** Uniqueness checked in Python only covers the data Python happens to see.
3. **Never swallow exceptions around features.** `suppress(Exception)` turned a crash into a feature that silently never worked.
4. **Lock the whole dependency tree.** "It worked when I built it" means nothing a year later without a lockfile.
5. **Free tiers have expiry dates.** Know the limits (25 MB Redis, 30-day Postgres, sleeping instances) before designing around them.

## Future improvements

- Webhook delivery log (status, response time) with retries and HMAC signing
- Alembic migrations instead of `create_all()`
- Object storage for uploads so web and worker can scale separately
- Use Postgres `COPY` into a staging table for faster bulk imports

---

Contact: vedpawar1410@gmail.com
