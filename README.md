# Product Importer - FastAPI + Celery + Postgres + Redis

A production-ready product import system with CSV processing, async task management, and webhook notifications.

## 🏗️ Architecture

```
┌─────────────┐      ┌──────────────┐      ┌─────────────┐
│   FastAPI   │─────▶│    Redis     │◀─────│   Celery    │
│   (Web)     │      │  (Broker)    │      │  (Worker)   │
└─────┬───────┘      └──────────────┘      └──────┬──────┘
      │                                             │
      │              ┌──────────────┐              │
      └─────────────▶│  PostgreSQL  │◀─────────────┘
                     │  (Database)  │
                     └──────────────┘
```

## ✨ Features

- **CSV Import**: Upload large CSV files with batch processing
- **Async Processing**: Celery workers handle imports asynchronously
- **Real-time Progress**: Redis-based progress tracking with WebSocket-ready architecture
- **Product Management**: Full CRUD API with pagination and filtering
- **Webhook System**: Event-driven notifications for import completion
- **Docker Compose**: Full containerized setup for development and production
- **Modern UI**: Beautiful frontend with real-time status updates

## 🚀 Quick Start

### Prerequisites

- Docker 20.10+
- Docker Compose 2.0+

### Installation & Running

1. **Clone the repository**
   ```bash
   git clone <your-repo-url>
   cd product-importer
   ```

2. **Start all services**
   ```bash
   docker-compose down -v  # Clean previous data (optional)
   docker-compose up --build
   ```

3. **Access the application**
   - Frontend: http://localhost:8000
   - API Docs: http://localhost:8000/docs
   - Health Check: http://localhost:8000/health

## 📂 Project Structure

```
product-importer/
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI application entry point
│   ├── api/                       # API route handlers
│   │   ├── __init__.py
│   │   ├── product_router.py     # Product CRUD endpoints
│   │   ├── upload_router.py      # CSV upload & status endpoints
│   │   └── webhook_router.py     # Webhook management endpoints
│   ├── core/                      # Core configuration
│   │   ├── __init__.py
│   │   ├── config.py             # Settings (Pydantic v2)
│   │   ├── database.py           # SQLAlchemy setup (sync + async)
│   │   └── celery_app.py         # Celery configuration & tasks
│   ├── models/                    # SQLAlchemy ORM models
│   │   ├── __init__.py
│   │   ├── product.py
│   │   └── webhook.py
│   ├── schemas/                   # Pydantic schemas
│   │   ├── __init__.py
│   │   ├── product.py
│   │   └── webhook.py
│   └── services/                  # Business logic
│       ├── __init__.py
│       ├── csv_importer.py       # CSV parsing & batch import
│       ├── product_service.py    # Product upsert logic
│       ├── webhook_service.py    # Webhook dispatch
│       └── webhook_sender.py     # HTTP webhook sender
├── frontend/                      # Static frontend files
│   ├── index.html                # CSV upload page
│   ├── products.html             # Product management page
│   ├── webhooks.html             # Webhook configuration page
│   ├── app.js                    # Frontend logic
│   └── styles.css                # Styling
├── docker-compose.yml            # Multi-container orchestration
├── Dockerfile                    # Web service image
├── Dockerfile.worker             # Worker service image
├── requirements.txt              # Python dependencies
├── run_web.sh                    # Web entrypoint script
├── run_worker.sh                 # Worker entrypoint script
└── README.md                     # This file
```

## 🔧 Configuration

Environment variables are set in `docker-compose.yml`:

### Web Service
```yaml
DATABASE_URL: postgresql://postgres:postgres@db:5432/products
CELERY_BROKER_URL: redis://redis:6379/0
CELERY_RESULT_BACKEND: redis://redis:6379/0
UVICORN_WORKERS: 4
```

### Worker Service
```yaml
DATABASE_URL: postgresql://postgres:postgres@db:5432/products
CELERY_BROKER_URL: redis://redis:6379/0
CELERY_RESULT_BACKEND: redis://redis:6379/0
CELERY_CONCURRENCY: 4
CELERY_LOG_LEVEL: info
```

## 📊 API Endpoints

### Upload & Status
- `POST /upload/start` - Upload CSV file, returns task_id
- `GET /upload/status/{task_id}` - Get import progress & status

### Products
- `GET /products` - List products (with pagination & filters)
- `POST /products` - Create a product
- `PUT /products/{id}` - Update a product
- `DELETE /products/{id}` - Delete a product
- `DELETE /products/all` - Bulk delete (with filters)

### Webhooks
- `GET /webhooks` - List registered webhooks
- `POST /webhooks` - Register a webhook
- `DELETE /webhooks/{id}` - Delete a webhook
- `POST /webhooks/test/{event}` - Test webhook dispatch

## 🔄 CSV Import Flow

1. **Upload** → User uploads CSV via `/upload/start`
2. **Save** → File saved to `/shared` volume (accessible by worker)
3. **Enqueue** → Celery task queued with task_id
4. **Process** → Worker reads CSV in batches (default 1000 rows)
5. **Upsert** → Products inserted/updated in PostgreSQL
6. **Progress** → Redis stores progress (processed/total)
7. **Poll** → Frontend polls `/upload/status/{task_id}`
8. **Complete** → Status updated, webhook triggered

## 📝 CSV Format

Expected CSV columns:
```csv
sku,name,description,price,active
SKU001,Product Name,Product description,29.99,true
SKU002,Another Product,More details,49.99,false
```

**Required Fields:**
- `sku` (string, unique, case-insensitive)
- `name` (string)

**Optional Fields:**
- `description` (text)
- `price` (float)
- `active` (boolean, default: true)

## 🐳 Docker Services

### web (FastAPI)
- **Image**: Python 3.11 slim
- **Port**: 8000
- **Purpose**: HTTP API + static frontend
- **Command**: `uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4`

### worker (Celery)
- **Image**: Python 3.11 slim
- **Purpose**: Background task processing
- **Command**: `celery -A app.core.celery_app.celery_app worker --loglevel info --concurrency 4`

### db (PostgreSQL 15)
- **Port**: 5432 (internal)
- **Database**: `products`
- **User/Pass**: `postgres/postgres`

### redis (Redis 7)
- **Port**: 6379
- **Purpose**: Celery broker + result backend + progress tracking

## 🛠️ Development

### View Logs
```bash
docker-compose logs -f web      # FastAPI logs
docker-compose logs -f worker   # Celery logs
docker-compose logs -f db       # PostgreSQL logs
docker-compose logs -f redis    # Redis logs
```

### Restart Services
```bash
docker-compose restart web      # Restart web only
docker-compose restart worker   # Restart worker only
```

### Shell Access
```bash
docker exec -it product-importer-web bash
docker exec -it product-importer-worker bash
docker exec -it product-importer-db psql -U postgres -d products
```

### Database Access
```bash
# Connect to PostgreSQL
docker exec -it product-importer-db psql -U postgres -d products

# Run queries
SELECT COUNT(*) FROM products;
SELECT * FROM products LIMIT 10;
```

### Check Celery Status
```bash
docker exec -it product-importer-worker celery -A app.core.celery_app.celery_app inspect active
docker exec -it product-importer-worker celery -A app.core.celery_app.celery_app inspect stats
```

## 🧪 Testing

### Manual Test - Upload CSV
```bash
# Create test CSV
cat > test.csv << EOF
sku,name,description,price,active
TEST001,Test Product 1,Description 1,19.99,true
TEST002,Test Product 2,Description 2,29.99,true
TEST003,Test Product 3,Description 3,39.99,false
EOF

# Upload via curl
curl -X POST http://localhost:8000/upload/start \
  -F "file=@test.csv"

# Get status (replace TASK_ID)
curl http://localhost:8000/upload/status/TASK_ID
```

### Test Product API
```bash
# List products
curl http://localhost:8000/products

# Create product
curl -X POST http://localhost:8000/products \
  -H "Content-Type: application/json" \
  -d '{"sku":"API001","name":"API Product","price":99.99,"active":true}'

# Get with filters
curl "http://localhost:8000/products?name=API&active=true"
```

## ⚠️ Troubleshooting

### Issue: Import fails with "File not found"
**Solution**: Ensure `/shared` volume is mounted in both web and worker containers

### Issue: No progress updates
**Solution**: Check Redis connection and ensure task_id matches between upload and status calls

### Issue: Database connection errors
**Solution**: Verify DATABASE_URL environment variable and ensure PostgreSQL is running

### Issue: Celery tasks not processing
**Solution**: Check worker logs and ensure Redis broker is accessible

### Issue: Frontend not loading
**Solution**: Verify static files are mounted at `/code/frontend` in the web container

## 📈 Performance Tuning

### For Large CSV Files (100K+ rows)

1. **Increase batch size** (csv_importer.py):
   ```python
   batch_size: int = 5000  # Default is 1000
   ```

2. **Increase worker concurrency**:
   ```yaml
   CELERY_CONCURRENCY: 8  # Default is 4
   ```

3. **Increase database connections** (database.py):
   ```python
   pool_size=20, max_overflow=40
   ```

### For High API Traffic

1. **Increase Uvicorn workers**:
   ```yaml
   UVICORN_WORKERS: 8  # Default is 4
   ```

2. **Add connection pooling**:
   ```python
   # In database.py
   pool_pre_ping=True,
   pool_recycle=3600
   ```

## 🔒 Security Notes

For production deployment:

1. **Change default passwords** in docker-compose.yml
2. **Use environment files** instead of hardcoded values
3. **Enable SSL/TLS** for PostgreSQL and Redis
4. **Add authentication** to API endpoints
5. **Validate CSV input** more strictly
6. **Rate limit** upload endpoints
7. **Use secrets management** (Docker secrets, AWS Secrets Manager, etc.)

## 📦 Dependencies

Key Python packages:
- **FastAPI** - Modern web framework
- **Uvicorn** - ASGI server
- **SQLAlchemy 2.0+** - ORM with async support
- **asyncpg** - Async PostgreSQL driver
- **Celery** - Distributed task queue
- **Redis** - In-memory data store
- **Pydantic 2.7+** - Data validation
- **pydantic-settings** - Settings management

## 🐛 Known Issues

None at this time. All critical bugs have been fixed:
- ✅ Pydantic v2 compatibility
- ✅ Database connection consistency
- ✅ Async/sync SQLAlchemy usage
- ✅ Import path resolution
- ✅ Environment variable loading
- ✅ Shared volume access

## 📄 License

[Your License Here]

## 👥 Contributing

[Your Contributing Guidelines Here]

## 📞 Support

For issues and questions:
- Create an issue on GitHub
- Contact: [Your Contact Info]

---

**Built with ❤️ using FastAPI, Celery, PostgreSQL, and Redis**
