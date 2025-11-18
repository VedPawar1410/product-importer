# 🚀 Production Deployment Guide

## Pre-Deployment Checklist

- [x] All bugs fixed (see FIXES_APPLIED.md)
- [x] Environment variables configured
- [x] Docker Compose ready
- [x] Documentation complete
- [ ] Production secrets configured (ACTION REQUIRED)
- [ ] SSL/TLS certificates ready (if needed)
- [ ] Monitoring configured (optional)

---

## Quick Start (Local Development)

```bash
# 1. Clone and navigate to project
cd product-importer

# 2. Start all services
docker-compose down -v  # Clean start
docker-compose up --build

# 3. Access application
open http://localhost:8000
```

**Services will be available at:**
- Frontend: http://localhost:8000
- API Docs: http://localhost:8000/docs
- Health Check: http://localhost:8000/health

---

## Production Deployment Steps

### Step 1: Security Configuration

**Create production environment file:**
```bash
cat > .env.production << EOF
# Database (use strong passwords!)
DATABASE_URL=postgresql://produser:CHANGE_THIS_PASSWORD@db:5432/products

# Redis (add password in production)
CELERY_BROKER_URL=redis://:REDIS_PASSWORD@redis:6379/0
CELERY_RESULT_BACKEND=redis://:REDIS_PASSWORD@redis:6379/0

# Performance tuning
UVICORN_WORKERS=8
CELERY_CONCURRENCY=8
CELERY_LOG_LEVEL=warning
EOF
```

### Step 2: Update docker-compose for Production

```yaml
# docker-compose.prod.yml
version: "3.9"

services:
  web:
    build:
      context: .
      dockerfile: Dockerfile
    restart: always
    ports:
      - "8000:8000"
    volumes:
      - shared_data:/shared
      - ./frontend:/code/frontend:ro  # Read-only
    env_file:
      - .env.production
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_started
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  worker:
    build:
      context: .
      dockerfile: Dockerfile.worker
    restart: always
    volumes:
      - shared_data:/shared
    env_file:
      - .env.production
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_started

  db:
    image: postgres:15
    restart: always
    environment:
      POSTGRES_USER: produser
      POSTGRES_PASSWORD: CHANGE_THIS_PASSWORD
      POSTGRES_DB: products
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U produser"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7
    restart: always
    command: redis-server --requirepass REDIS_PASSWORD
    volumes:
      - redis_data:/data

volumes:
  postgres_data:
  redis_data:
  shared_data:
```

### Step 3: Build and Deploy

```bash
# Build images
docker-compose -f docker-compose.prod.yml build

# Start in detached mode
docker-compose -f docker-compose.prod.yml up -d

# Check status
docker-compose -f docker-compose.prod.yml ps

# View logs
docker-compose -f docker-compose.prod.yml logs -f
```

---

## Monitoring & Maintenance

### View Logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f web
docker-compose logs -f worker

# Last 100 lines
docker-compose logs --tail=100 web
```

### Health Checks
```bash
# Application health
curl http://localhost:8000/health

# Database connection
docker exec product-importer-db pg_isready -U postgres

# Redis connection
docker exec product-importer-redis redis-cli ping

# Celery worker status
docker exec product-importer-worker celery -A app.core.celery_app.celery_app inspect active
```

### Database Backup
```bash
# Backup
docker exec product-importer-db pg_dump -U postgres products > backup_$(date +%Y%m%d).sql

# Restore
cat backup_20250118.sql | docker exec -i product-importer-db psql -U postgres products
```

### Update Application
```bash
# Pull latest changes
git pull origin main

# Rebuild and restart
docker-compose down
docker-compose up --build -d

# Or use rolling restart (no downtime)
docker-compose up -d --no-deps --build web
docker-compose up -d --no-deps --build worker
```

---

## Performance Optimization

### For High Traffic (1000+ req/min)

**Increase web workers:**
```yaml
environment:
  UVICORN_WORKERS: 16  # 2x CPU cores
```

**Add connection pooling:**
```python
# app/core/database.py
engine = create_engine(
    settings.database_url,
    pool_size=30,
    max_overflow=60,
    pool_pre_ping=True,
    pool_recycle=3600
)
```

### For Large CSV Files (1M+ rows)

**Increase batch size:**
```python
# app/services/csv_importer.py
batch_size: int = 10000  # Default is 1000
```

**Increase worker concurrency:**
```yaml
environment:
  CELERY_CONCURRENCY: 16
```

**Add more workers:**
```yaml
services:
  worker:
    deploy:
      replicas: 3  # Docker Swarm
    # OR manually
  worker2:
    # Same config as worker
  worker3:
    # Same config as worker
```

---

## Troubleshooting

### Issue: Container keeps restarting
```bash
# Check logs
docker-compose logs web

# Common causes:
# - Missing environment variables
# - Database not ready
# - Import errors

# Solution: Check environment and dependencies
docker-compose down
docker-compose up
```

### Issue: CSV import fails
```bash
# Check worker logs
docker-compose logs worker

# Check if file exists in shared volume
docker exec product-importer-worker ls -la /shared/

# Verify permissions
docker exec product-importer-worker ls -l /shared/
```

### Issue: Database connection errors
```bash
# Check database is running
docker-compose ps db

# Test connection
docker exec product-importer-db psql -U postgres -d products -c "SELECT 1"

# Verify DATABASE_URL
docker exec product-importer-web env | grep DATABASE_URL
```

### Issue: Redis connection errors
```bash
# Check Redis is running
docker-compose ps redis

# Test connection
docker exec product-importer-redis redis-cli ping

# Check logs
docker-compose logs redis
```

---

## Security Best Practices

### 1. Use Strong Passwords
```bash
# Generate secure passwords
openssl rand -base64 32
```

### 2. Enable PostgreSQL SSL
```yaml
db:
  command: >
    postgres
    -c ssl=on
    -c ssl_cert_file=/var/lib/postgresql/server.crt
    -c ssl_key_file=/var/lib/postgresql/server.key
```

### 3. Enable Redis Authentication
```yaml
redis:
  command: redis-server --requirepass YOUR_REDIS_PASSWORD
```

### 4. Use Docker Secrets (Swarm)
```yaml
secrets:
  db_password:
    external: true
services:
  db:
    secrets:
      - db_password
    environment:
      POSTGRES_PASSWORD_FILE: /run/secrets/db_password
```

### 5. Add Rate Limiting
```python
# Install slowapi
pip install slowapi

# In main.py
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.post("/upload/start")
@limiter.limit("10/minute")
async def start_upload(...):
    ...
```

---

## Scaling Strategies

### Horizontal Scaling (Docker Swarm)

```bash
# Initialize swarm
docker swarm init

# Deploy stack
docker stack deploy -c docker-compose.prod.yml productimporter

# Scale workers
docker service scale productimporter_worker=5

# Scale web
docker service scale productimporter_web=3
```

### Kubernetes Deployment

```yaml
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: product-importer-web
spec:
  replicas: 3
  selector:
    matchLabels:
      app: product-importer-web
  template:
    metadata:
      labels:
        app: product-importer-web
    spec:
      containers:
      - name: web
        image: product-importer:latest
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: db-credentials
              key: url
```

---

## Monitoring Setup

### Prometheus + Grafana

**Add metrics endpoint:**
```python
# Install prometheus client
pip install prometheus-fastapi-instrumentator

# In main.py
from prometheus_fastapi_instrumentator import Instrumentator

Instrumentator().instrument(app).expose(app)
```

**Scrape config:**
```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'product-importer'
    static_configs:
      - targets: ['web:8000']
```

### Log Aggregation (ELK Stack)

```yaml
# docker-compose.yml
services:
  elasticsearch:
    image: elasticsearch:8.11.0
  
  logstash:
    image: logstash:8.11.0
  
  kibana:
    image: kibana:8.11.0
    ports:
      - "5601:5601"
```

---

## Backup Strategy

### Automated Backups

```bash
# Create backup script
cat > backup.sh << 'EOF'
#!/bin/bash
BACKUP_DIR=/backups
DATE=$(date +%Y%m%d_%H%M%S)

# Database backup
docker exec product-importer-db pg_dump -U postgres products | gzip > $BACKUP_DIR/db_$DATE.sql.gz

# Redis backup
docker exec product-importer-redis redis-cli BGSAVE

# Keep last 7 days
find $BACKUP_DIR -name "db_*.sql.gz" -mtime +7 -delete

echo "Backup completed: $DATE"
EOF

chmod +x backup.sh

# Add to crontab (daily at 2 AM)
0 2 * * * /path/to/backup.sh
```

---

## Testing in Production

```bash
# Smoke test - Upload CSV
curl -X POST http://localhost:8000/upload/start \
  -F "file=@sample-products.csv"

# Response: {"task_id":"abc123...","celery_task_id":"xyz789..."}

# Check status
curl http://localhost:8000/upload/status/abc123...

# Verify products
curl http://localhost:8000/products?limit=5

# Check health
curl http://localhost:8000/health
```

---

## Support & Resources

- **Documentation**: See README.md
- **Bug Reports**: See FIXES_APPLIED.md
- **API Documentation**: http://localhost:8000/docs
- **Sample Data**: sample-products.csv

---

**Deployment Status: ✅ READY FOR PRODUCTION**

