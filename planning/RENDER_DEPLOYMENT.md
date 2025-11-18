# 🚀 Render.com Deployment Guide

## Overview

This guide will walk you through deploying the Product Importer application to Render.com using the automated Blueprint (render.yaml).

## ✅ Pre-Deployment Checklist

All deployment preparations have been completed:

- ✅ Environment variables configured for Render (POSTGRES_URL, REDIS_URL)
- ✅ Storage paths updated to use `/data` (Render's persistent disk)
- ✅ Dockerfiles optimized for production
- ✅ `render.yaml` blueprint created
- ✅ Docker builds tested successfully
- ✅ `.gitignore` updated for deployment
- ✅ Local development still works with Docker Compose

## 📋 What's Deployed

The application consists of 4 services on Render:

1. **Web Service** (FastAPI) - HTTP API + Frontend
2. **Worker Service** (Celery) - Background task processing
3. **PostgreSQL Database** - Data storage
4. **Redis Instance** - Message broker + cache

## 🎯 Deployment Steps

### Step 1: Push to GitHub

1. **Create a new GitHub repository**

```bash
# Initialize git if not already done
git init

# Add all files
git add .

# Commit changes
git commit -m "Ready for Render deployment"

# Add your GitHub remote (replace with your repository URL)
git remote add origin https://github.com/VedPawar1410/product-importer.git

# Push to GitHub
git push -u origin main
```

### Step 2: Deploy to Render

#### Option A: Using Render Blueprint (Recommended)

1. **Sign up/Login to Render**: https://render.com

2. **Create New Blueprint Instance**:
   - Go to https://dashboard.render.com/select-repo
   - Click "New" → "Blueprint"
   - Connect your GitHub repository
   - Select the repository: `YOUR_USERNAME/product-importer`
   - Render will automatically detect `render.yaml`

3. **Review Services**:
   - `product-importer-web` (Web Service)
   - `product-importer-worker` (Worker Service)
   - `product-importer-db` (PostgreSQL)
   - `product-importer-redis` (Redis)

4. **Click "Apply"**:
   - Render will automatically:
     - Create all 4 services
     - Wire environment variables
     - Set up persistent disk for uploads
     - Start building Docker images

5. **Wait for Deployment** (5-10 minutes):
   - Database provisioning: ~2 minutes
   - Redis provisioning: ~1 minute
   - Web service build: ~3-5 minutes
   - Worker service build: ~3-5 minutes

#### Option B: Manual Service Creation

If you prefer manual setup:

1. **Create PostgreSQL Database**:
   - New → PostgreSQL
   - Name: `product-importer-db`
   - Database: `products`
   - Plan: Free

2. **Create Redis Instance**:
   - New → Redis
   - Name: `product-importer-redis`
   - Plan: Free

3. **Create Web Service**:
   - New → Web Service
   - Connect repository
   - Name: `product-importer-web`
   - Runtime: Docker
   - Dockerfile Path: `./Dockerfile`
   - Plan: Free
   - Add Disk:
     - Name: `product-uploads`
     - Mount Path: `/data`
     - Size: 1 GB
   - Environment Variables:
     - `POSTGRES_URL`: [Link to database]
     - `REDIS_URL`: [Link to Redis]
     - `UVICORN_WORKERS`: `1`

4. **Create Worker Service**:
   - New → Background Worker
   - Connect repository
   - Name: `product-importer-worker`
   - Runtime: Docker
   - Dockerfile Path: `./Dockerfile.worker`
   - Plan: Free
   - Add Disk:
     - Name: `product-uploads` (same as web)
     - Mount Path: `/data`
     - Size: 1 GB
   - Environment Variables:
     - `POSTGRES_URL`: [Link to database]
     - `REDIS_URL`: [Link to Redis]
     - `CELERY_CONCURRENCY`: `2`
     - `CELERY_LOG_LEVEL`: `info`

### Step 3: Verify Deployment

1. **Access Your Application**:
   ```
   https://product-importer-web.onrender.com
   ```

2. **Check Health Endpoint**:
   ```bash
   curl https://product-importer-web.onrender.com/health
   # Expected: {"status":"ok"}
   ```

3. **Access API Documentation**:
   ```
   https://product-importer-web.onrender.com/docs
   ```

4. **Test CSV Upload**:
   - Visit the web interface
   - Upload a test CSV file
   - Monitor progress in real-time

### Step 4: Monitor Services

Check each service in the Render Dashboard:

1. **Web Service Logs**:
   - Dashboard → product-importer-web → Logs
   - Look for: "Uvicorn running on http://0.0.0.0:8000"

2. **Worker Service Logs**:
   - Dashboard → product-importer-worker → Logs
   - Look for: "celery@... ready"

3. **Database Status**:
   - Dashboard → product-importer-db
   - Verify: "Available"

4. **Redis Status**:
   - Dashboard → product-importer-redis
   - Verify: "Available"

## 🔧 Configuration Details

### Environment Variables

The application automatically reads these Render-provided variables:

| Variable | Source | Purpose |
|----------|--------|---------|
| `POSTGRES_URL` | Render Database | PostgreSQL connection string |
| `REDIS_URL` | Render Redis | Redis connection string |
| `UVICORN_WORKERS` | Manual (default: 1) | Number of web workers |
| `CELERY_CONCURRENCY` | Manual (default: 2) | Number of Celery workers |
| `CELERY_LOG_LEVEL` | Manual (default: info) | Logging verbosity |

### Persistent Storage

Both web and worker services share a persistent disk:

- **Mount Path**: `/data`
- **Upload Directory**: `/data/uploads`
- **Size**: 1 GB (expandable)
- **Shared**: Yes (same disk across web + worker)

This ensures uploaded CSV files are accessible to both services.

### Resource Limits (Free Tier)

| Service | RAM | CPU | Disk |
|---------|-----|-----|------|
| Web | 512 MB | 0.1 vCPU | 1 GB |
| Worker | 512 MB | 0.1 vCPU | 1 GB |
| PostgreSQL | 256 MB | Shared | 1 GB |
| Redis | 25 MB | Shared | 25 MB |

**Note**: Free tier services spin down after 15 minutes of inactivity.

## 🔍 Troubleshooting

### Issue: Services not starting

**Symptoms**: Build succeeds but service shows "Failed"

**Solutions**:
```bash
# Check logs in Render Dashboard
# Common causes:
# 1. Missing environment variables
# 2. Database not ready
# 3. Port binding issues
```

**Fix**:
- Verify `POSTGRES_URL` and `REDIS_URL` are set
- Check database is "Available" before deploying web/worker
- Ensure health check endpoint (`/health`) is accessible

### Issue: CSV upload fails

**Symptoms**: Upload returns success but worker doesn't process

**Solutions**:
```bash
# Check worker logs in Render Dashboard
# Common causes:
# 1. Disk not mounted
# 2. Permission issues
# 3. Worker not connected to Redis
```

**Fix**:
- Verify disk is mounted at `/data` on both services
- Check worker logs for Celery connection errors
- Ensure Redis is "Available"

### Issue: Slow performance

**Symptoms**: Requests timeout or are very slow

**Solutions**:
```bash
# Free tier limitations:
# - Services spin down after 15 min inactivity
# - First request after spindown takes 30-60 seconds
# - Limited CPU/RAM resources
```

**Fix** (Upgrade to paid plan):
- Starter plan: $7/month per service
- No spin-down
- More resources (512 MB → 2 GB RAM)

### Issue: Database connection errors

**Symptoms**: "could not connect to server"

**Solutions**:
```bash
# Check database status in Render Dashboard
# Common causes:
# 1. Database still provisioning
# 2. POSTGRES_URL incorrect
# 3. SSL issues
```

**Fix**:
- Wait for database to show "Available"
- Verify connection string format
- Render PostgreSQL requires SSL (handled automatically)

### Issue: Redis connection errors

**Symptoms**: "Error connecting to Redis"

**Solutions**:
```bash
# Check Redis status in Render Dashboard
# Common causes:
# 1. Redis still provisioning
# 2. REDIS_URL incorrect
# 3. Connection limit reached (free tier: 10)
```

**Fix**:
- Wait for Redis to show "Available"
- Verify connection string format
- Monitor active connections

### Issue: Disk full errors

**Symptoms**: "No space left on device"

**Solutions**:
```bash
# Free tier: 1 GB disk
# CSV files accumulate in /data/uploads
```

**Fix**:
- Increase disk size in Render Dashboard
- Implement cleanup job (delete old CSVs)
- Upgrade to paid plan for more storage

## 🚀 Upgrading from Free Tier

### Recommended Paid Plan Setup

For production use, consider:

1. **Web Service**: Starter ($7/month)
   - 512 MB RAM
   - No spin-down
   - Custom domain support

2. **Worker Service**: Starter ($7/month)
   - 512 MB RAM
   - Continuous background processing

3. **PostgreSQL**: Starter ($7/month)
   - 256 MB RAM → 1 GB RAM
   - 1 GB disk → 10 GB disk
   - High availability option

4. **Redis**: Starter ($10/month)
   - 25 MB → 100 MB
   - 10 connections → 100 connections
   - Persistence enabled

**Total**: ~$31/month for production-ready setup

### Scaling Strategies

1. **Increase Worker Concurrency**:
   ```yaml
   envVars:
     - key: CELERY_CONCURRENCY
       value: 4  # Up from 2
   ```

2. **Add More Workers**:
   - Duplicate worker service
   - Both will pull from same Redis queue
   - Parallel processing of CSV imports

3. **Increase Web Workers**:
   ```yaml
   envVars:
     - key: UVICORN_WORKERS
       value: 4  # Up from 1
   ```

4. **Upgrade Disk Size**:
   - Dashboard → Service → Disk
   - Increase from 1 GB to 10 GB or more

## 📊 Monitoring

### Built-in Render Monitoring

- **Metrics**: CPU, Memory, Disk usage
- **Logs**: Real-time log streaming
- **Alerts**: Email notifications for failures

### Health Checks

Render automatically monitors:
```
GET /health
Expected: 200 OK
Frequency: Every 30 seconds
```

### Manual Checks

```bash
# Test API
curl https://product-importer-web.onrender.com/products

# Check specific endpoints
curl https://product-importer-web.onrender.com/docs

# Upload test CSV
curl -X POST https://product-importer-web.onrender.com/upload/start \
  -F "file=@test.csv"
```

## 🔐 Security Considerations

### Render Handles

- ✅ SSL/TLS certificates (automatic)
- ✅ HTTPS for all services
- ✅ Environment variable encryption
- ✅ Database connection security
- ✅ DDoS protection

### You Should Add

1. **API Authentication**:
   ```python
   # Add API key middleware
   # Or OAuth2 integration
   ```

2. **Rate Limiting**:
   ```python
   # Use slowapi or fastapi-limiter
   ```

3. **CORS Configuration**:
   ```python
   # Configure allowed origins in production
   ```

4. **Input Validation**:
   ```python
   # Validate CSV structure before processing
   ```

## 🔄 Updates & Redeployment

### Automatic Deployments

Render automatically redeploys when you push to GitHub:

```bash
# Make changes locally
git add .
git commit -m "Update feature"
git push origin main

# Render automatically:
# 1. Detects push
# 2. Rebuilds Docker images
# 3. Deploys with zero-downtime
```

### Manual Deployment

From Render Dashboard:
1. Go to service
2. Click "Manual Deploy"
3. Select branch
4. Click "Deploy"

### Rollback

1. Go to service → "Events"
2. Find previous successful deploy
3. Click "Rollback to this version"

## 📦 Sample CSV for Testing

Create `test-products.csv`:

```csv
sku,name,description,price,active
TEST001,Test Product 1,A sample product,19.99,true
TEST002,Test Product 2,Another sample,29.99,true
TEST003,Test Product 3,Final test item,39.99,false
```

Upload via:
```bash
curl -X POST https://product-importer-web.onrender.com/upload/start \
  -F "file=@test-products.csv"
```

## 🎓 Best Practices

1. **Use Blueprint**: Always deploy via `render.yaml` for consistency
2. **Monitor Logs**: Check logs after each deployment
3. **Test Health Endpoint**: Verify `/health` returns 200
4. **Staged Rollouts**: Test in a separate environment first
5. **Backup Data**: Export PostgreSQL data periodically
6. **Document Changes**: Keep this guide updated

## 📞 Support Resources

- **Render Docs**: https://render.com/docs
- **Render Status**: https://status.render.com
- **Render Community**: https://community.render.com
- **Project README**: See README.md
- **API Docs**: `/docs` endpoint

---

## 🎉 Deployment Complete!

Your application is now live at:
```
https://product-importer-web.onrender.com
```

Next steps:
1. ✅ Test CSV upload functionality
2. ✅ Configure custom domain (optional)
3. ✅ Set up monitoring/alerts
4. ✅ Consider upgrading to paid plan for production
5. ✅ Implement additional security measures

---

**Built with ❤️ | Deployed on Render**

