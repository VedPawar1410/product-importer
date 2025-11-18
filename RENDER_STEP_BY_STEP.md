# 🚀 Render.com Deployment - Complete Step-by-Step Guide

**Time Required**: 20-30 minutes  
**Cost**: $0 (Free Tier)  
**Result**: Fully functional product importer at `https://product-importer-web.onrender.com`

---

## 📋 What You're Deploying

Your application consists of 4 interconnected services:

```
┌─────────────────────┐
│  FastAPI Web (1)    │ ← User uploads CSV here
│  Serves frontend    │
└──────────┬──────────┘
           │
           ↓
┌─────────────────────┐
│  Celery Worker (2)  │ ← Processes CSV in background
│  Background tasks    │
└──────────┬──────────┘
           │
           ↓
┌─────────────────────┐     ┌─────────────────────┐
│  PostgreSQL (3)     │     │  Redis (4)          │
│  Stores products    │     │  Task queue         │
└─────────────────────┘     └─────────────────────┘
```

All 4 services must be running for the app to work.

---

## 🎯 Pre-Flight Checklist

Before starting, verify you have:

- [ ] A GitHub account
- [ ] A Render.com account (can create during deployment)
- [ ] Your project code (you have this)
- [ ] 20-30 minutes of uninterrupted time

---

# PART 1: Push Code to GitHub

## Step 1: Check Current Git Status

```bash
cd /Users/vedpawar/ai/product-importer
git status
```

**What you'll see**:
- If you see "fatal: not a git repository", continue to Step 2
- If you see modified files, continue to Step 3
- If you see "nothing to commit", skip to Step 5

---

## Step 2: Initialize Git Repository (if needed)

```bash
# Initialize git
git init

# Add main branch
git branch -M main
```

**Expected output**:
```
Initialized empty Git repository in /Users/vedpawar/ai/product-importer/.git/
```

---

## Step 3: Stage All Files

```bash
# Add all files to staging
git add .

# Verify what will be committed
git status
```

**What you should see**:
- All your project files listed in green
- Files like `.env`, `__pycache__/`, `/data/` should NOT appear (they're ignored)

**If you see `.env` or `__pycache__/` in the list**:
```bash
# These should be ignored - verify .gitignore exists
cat .gitignore
```

---

## Step 4: Commit Your Code

```bash
git commit -m "Initial commit - Ready for Render deployment"
```

**Expected output**:
```
[main (root-commit) abc1234] Initial commit - Ready for Render deployment
 XX files changed, XXX insertions(+)
```

---

## Step 5: Create GitHub Repository

### 5a. Go to GitHub

Open your browser and navigate to:
```
https://github.com/new
```

### 5b. Fill in Repository Details

| Field | Value |
|-------|-------|
| **Repository name** | `product-importer` |
| **Description** | FastAPI + Celery Product Importer |
| **Visibility** | Public (required for free Render deployment) |
| **Initialize with README** | ❌ NO (you already have code) |
| **Add .gitignore** | ❌ NO (you already have one) |
| **Choose a license** | Optional (skip for now) |

### 5c. Click "Create repository"

---

## Step 6: Connect Local Repository to GitHub

After creating the repository, GitHub shows you commands. Copy the section under **"…or push an existing repository from the command line"**

It will look like this (with YOUR username):

```bash
git remote add origin https://github.com/YOUR_USERNAME/product-importer.git
git branch -M main
git push -u origin main
```

**IMPORTANT**: Replace `YOUR_USERNAME` with your actual GitHub username!

### Example:
If your GitHub username is `vedpawar123`, use:
```bash
git remote add origin https://github.com/vedpawar123/product-importer.git
git branch -M main
git push -u origin main
```

---

## Step 7: Push Code to GitHub

Run the commands from Step 6. You'll be prompted for credentials:

**If prompted for username/password**:
- GitHub no longer accepts passwords
- You need a Personal Access Token (PAT)
- Go to: https://github.com/settings/tokens
- Click "Generate new token (classic)"
- Select scopes: `repo` (all checkboxes)
- Copy the token and use it as your password

**Expected output**:
```
Enumerating objects: XX, done.
Counting objects: 100% (XX/XX), done.
...
To https://github.com/YOUR_USERNAME/product-importer.git
 * [new branch]      main -> main
Branch 'main' set up to track remote branch 'main' from 'origin'.
```

---

## Step 8: Verify GitHub Upload

Open your browser and go to:
```
https://github.com/YOUR_USERNAME/product-importer
```

**You should see**:
- All your project files
- `render.yaml` in the root directory
- `README.md` displayed at the bottom
- Frontend folder visible
- Dockerfiles visible

**If render.yaml is missing**:
```bash
# Verify it exists locally
ls -la render.yaml

# If it exists but wasn't pushed
git add render.yaml
git commit -m "Add render.yaml"
git push
```

---

# PART 2: Deploy to Render

## Step 9: Create Render Account

### 9a. Go to Render

Open your browser:
```
https://render.com
```

### 9b. Sign Up

- Click "Get Started" or "Sign Up"
- Choose: **"Sign up with GitHub"** (easiest option)
- Authorize Render to access your GitHub account
- Complete any email verification if required

**Expected**: You'll be redirected to Render Dashboard

---

## Step 10: Connect GitHub Repository to Render

### 10a. From Render Dashboard

Click the blue "New +" button in the top right corner

### 10b. Select "Blueprint"

You'll see several options:
- Web Service
- Background Worker
- **Blueprint** ← SELECT THIS ONE
- Cron Job
- etc.

**Why Blueprint?**: It deploys all 4 services at once using `render.yaml`

---

## Step 11: Configure Blueprint

### 11a. Connect Repository

On the "Create a new Blueprint Instance" page:

1. **Select repository source**: GitHub (should be pre-selected)
2. **Connect a repository**: 
   - If you see your repository listed, click on it
   - If not, click "Configure GitHub App" to grant access

3. **Search for your repository**: Type `product-importer`
4. **Click "Connect"** next to `YOUR_USERNAME/product-importer`

### 11b. Review Blueprint Configuration

Render will automatically detect `render.yaml` and show:

**Services to be created**:
```
✓ product-importer-web (Web Service)
✓ product-importer-worker (Background Worker)
✓ product-importer-db (PostgreSQL Database)
✓ product-importer-redis (Redis)
```

**Environment Variables**:
- Render auto-wires `POSTGRES_URL` from database
- Render auto-wires `REDIS_URL` from Redis
- `UVICORN_WORKERS`: 1
- `CELERY_CONCURRENCY`: 2
- `CELERY_LOG_LEVEL`: info

**Disks**:
- `product-uploads` (1 GB) mounted at `/data` on both web and worker

### 11c. Give Blueprint Instance a Name

- **Instance Name**: `product-importer` (or leave default)
- This is just for organization in your dashboard

---

## Step 12: Deploy!

### 12a. Click "Apply"

This starts the deployment process. You'll be redirected to the Blueprint overview page.

### 12b. Watch the Progress

You'll see 4 services being created:

```
🔄 product-importer-db          Creating...
🔄 product-importer-redis       Creating...
🔄 product-importer-web         Waiting for dependencies...
🔄 product-importer-worker      Waiting for dependencies...
```

**This is NORMAL**: Web and worker wait for database and Redis to be ready first.

---

## Step 13: Monitor Deployment (10-15 minutes)

### 13a. Database Provisioning (2-3 minutes)

```
product-importer-db
Status: Provisioning → Available ✓
```

**What's happening**: Render is creating a PostgreSQL 15 instance

### 13b. Redis Provisioning (1-2 minutes)

```
product-importer-redis
Status: Creating → Available ✓
```

**What's happening**: Render is creating a Redis 7 instance

### 13c. Web Service Build (5-7 minutes)

Once database and Redis are ready:

```
product-importer-web
Status: Building...

Build logs:
==> Downloading cache...
==> Cloning from https://github.com/...
==> Building Docker image...
    FROM python:3.11-slim
    ...
    [build logs]
    ...
==> Build complete
==> Deploying...
==> Starting service...
Status: Live ✓
```

**What's happening**: 
1. Cloning your repo
2. Building Docker image from `Dockerfile`
3. Starting FastAPI server
4. Running health checks at `/health`

### 13d. Worker Service Build (5-7 minutes)

Simultaneously with web service:

```
product-importer-worker
Status: Building...

Build logs:
==> Building Docker image...
    FROM python:3.11-slim
    ...
    [build logs]
    ...
==> Build complete
==> Deploying...
==> Starting service...
Status: Running ✓
```

**What's happening**:
1. Building Docker image from `Dockerfile.worker`
2. Starting Celery worker
3. Connecting to Redis and PostgreSQL

---

## Step 14: Verify All Services Are Healthy

### 14a. Check Dashboard

After 10-15 minutes, all services should show:

| Service | Status | Indicator |
|---------|--------|-----------|
| product-importer-web | Live | 🟢 Green dot |
| product-importer-worker | Running | 🟢 Green dot |
| product-importer-db | Available | 🟢 Green dot |
| product-importer-redis | Available | 🟢 Green dot |

### 14b. Get Your Application URL

Click on `product-importer-web` in the dashboard.

You'll see:
```
https://product-importer-web-XXXXX.onrender.com
```

**This is your live application URL!**

Copy this URL - you'll need it for testing.

---

# PART 3: Verify Deployment

## Step 15: Test Health Endpoint

### 15a. Open Terminal

```bash
# Replace with YOUR actual URL
curl https://product-importer-web-XXXXX.onrender.com/health
```

**Expected Response**:
```json
{"status":"ok"}
```

**If you get an error**:
- Service might still be starting (wait 1-2 minutes)
- Check logs in Step 16

---

## Step 16: Check Service Logs

### 16a. Web Service Logs

In Render Dashboard:
1. Click `product-importer-web`
2. Click "Logs" tab

**What to look for** (should see):
```
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

**Red flags** (should NOT see):
```
ERROR: Could not connect to database
ERROR: Connection refused
FAILED: Health check
```

### 16b. Worker Service Logs

In Render Dashboard:
1. Click `product-importer-worker`
2. Click "Logs" tab

**What to look for** (should see):
```
[INFO/MainProcess] Connected to redis://...
[INFO/MainProcess] celery@... ready.
[INFO/MainProcess] mingle: all alone
```

**Red flags** (should NOT see):
```
ERROR: Cannot connect to Redis
ERROR: Database connection failed
```

### 16c. Database Logs

In Render Dashboard:
1. Click `product-importer-db`
2. Click "Logs" tab

**What to look for** (should see):
```
PostgreSQL init process complete; ready for start up.
database system is ready to accept connections
```

### 16d. Redis Logs

In Render Dashboard:
1. Click `product-importer-redis`
2. Click "Info" tab (logs may not be available)

**Status should show**: Available ✓

---

## Step 17: Test Frontend

### 17a. Open in Browser

Navigate to:
```
https://product-importer-web-XXXXX.onrender.com
```

**What you should see**:
- Upload interface with "Choose CSV File" button
- Clean, modern UI
- No errors in browser console (press F12 to check)

**On first load** (FREE TIER ONLY):
- If service was asleep, first request takes 30-60 seconds
- You'll see a blank page or "Please wait..."
- This is NORMAL - refresh after 30 seconds
- Subsequent requests are fast

### 17b. Check API Documentation

Navigate to:
```
https://product-importer-web-XXXXX.onrender.com/docs
```

**What you should see**:
- Swagger UI (interactive API documentation)
- Endpoints listed:
  - GET /health
  - POST /upload/start
  - GET /upload/status/{task_id}
  - GET /products
  - POST /products
  - etc.

---

## Step 18: Test CSV Upload (Full End-to-End)

### 18a. Create Test CSV File

On your local machine:

```bash
cd /Users/vedpawar/ai/product-importer

# Create test file
cat > test-render.csv << 'EOF'
sku,name,description,price,active
RENDER001,Test Product 1,First test product,19.99,true
RENDER002,Test Product 2,Second test product,29.99,true
RENDER003,Test Product 3,Third test product,39.99,false
EOF
```

### 18b. Upload via Frontend

1. Go to: `https://product-importer-web-XXXXX.onrender.com`
2. Click "Choose CSV File"
3. Select `test-render.csv`
4. Click "Upload & Import"

**What happens next**:

**Step 1** (Immediate):
```
✓ File uploaded successfully
  Task ID: abc123def456...
  Status: QUEUED
```

**Step 2** (2-5 seconds):
```
Status: PROCESSING
Progress: 1/3 rows (33%)
```

**Step 3** (5-10 seconds):
```
Status: PROCESSING
Progress: 2/3 rows (67%)
```

**Step 4** (10-15 seconds):
```
Status: COMPLETED
Processed: 3 rows
```

### 18c. Upload via API (Alternative Method)

```bash
# Upload CSV
curl -X POST https://product-importer-web-XXXXX.onrender.com/upload/start \
  -F "file=@test-render.csv"

# Response:
{
  "task_id": "abc123def456",
  "celery_task_id": "xyz789..."
}

# Check status
curl https://product-importer-web-XXXXX.onrender.com/upload/status/abc123def456

# Response:
{
  "task_id": "abc123def456",
  "status": {
    "status": "COMPLETED",
    "processed": "3"
  },
  "progress": {
    "processed_rows": "3",
    "total_rows": "3"
  }
}
```

---

## Step 19: Verify Products in Database

### 19a. Via API

```bash
# List all products
curl https://product-importer-web-XXXXX.onrender.com/products

# Response:
{
  "total": 3,
  "items": [
    {
      "id": 1,
      "sku": "RENDER001",
      "name": "Test Product 1",
      "description": "First test product",
      "price": 19.99,
      "active": true,
      "created_at": "2025-11-18T...",
      "updated_at": "2025-11-18T..."
    },
    ...
  ]
}
```

### 19b. Via Frontend

1. Go to: `https://product-importer-web-XXXXX.onrender.com/products.html`
2. You should see a table with your 3 products
3. Try filtering, pagination, editing

---

## Step 20: Test Webhook System

### 20a. Register a Webhook

```bash
curl -X POST https://product-importer-web-XXXXX.onrender.com/webhooks \
  -H "Content-Type: application/json" \
  -d '{
    "event": "import.completed",
    "url": "https://webhook.site/your-unique-url"
  }'
```

**Tip**: Get a free webhook test URL at https://webhook.site

### 20b. Verify Webhook

```bash
curl https://product-importer-web-XXXXX.onrender.com/webhooks

# Should show your registered webhook
```

---

# PART 4: Understanding Render's Free Tier

## Important Free Tier Behaviors

### 1. **Service Spin-Down** ⚠️

**What happens**:
- After 15 minutes of inactivity, services "sleep"
- First request after sleep takes 30-60 seconds to wake up
- Subsequent requests are fast

**This affects**:
- Web service (FastAPI)
- Worker service (Celery)

**Does NOT affect**:
- Database (always on)
- Redis (always on)

**Solution**:
- Upgrade to paid plan ($7/month) for 24/7 uptime
- Or: Set up a free uptime monitor (e.g., UptimeRobot) to ping every 5 minutes

### 2. **Disk Persistence** ✓

**Good news**: 
- Your uploaded CSV files in `/data/uploads` persist even after spin-down
- Database data persists
- Redis data persists (with limitations)

### 3. **Build Minutes**

Free tier includes:
- 400 build minutes/month
- Each deployment uses ~5-10 minutes
- You can deploy ~40-80 times per month

### 4. **Resource Limits**

| Resource | Limit |
|----------|-------|
| RAM (Web) | 512 MB |
| RAM (Worker) | 512 MB |
| CPU (Web) | 0.1 vCPU |
| CPU (Worker) | 0.1 vCPU |
| Database Size | 1 GB |
| Disk Size | 1 GB |
| Redis Memory | 25 MB |

**Good for**:
- Development
- Testing
- Small demos
- Low traffic sites (<1000 requests/day)

**Not good for**:
- Production with high traffic
- Large CSV files (>100k rows)
- Concurrent users (>10)

---

# PART 5: Troubleshooting

## Problem 1: Services Won't Start

### Symptoms:
- Service shows "Deploy failed"
- Red indicator in dashboard

### Solution:

**Step 1**: Check build logs
```
Dashboard → product-importer-web → Logs tab
```

**Step 2**: Look for errors
```
ERROR: requirements.txt not found
ERROR: Cannot connect to database
ERROR: Port 8000 already in use
```

**Step 3**: Common fixes

**Error: "requirements.txt not found"**
```bash
# Verify file exists in repo
ls requirements.txt

# If missing, add it
git add requirements.txt
git commit -m "Add requirements"
git push
```

**Error: "Cannot connect to database"**
- Database is still provisioning (wait 2-3 minutes)
- Check `POSTGRES_URL` is set in environment variables

**Error: "Health check failed"**
- Service is starting (wait 1-2 minutes)
- Check `/health` endpoint is working

---

## Problem 2: CSV Upload Returns Error

### Symptoms:
- Upload button does nothing
- Error: "File upload failed"
- Status never changes from QUEUED

### Solution:

**Step 1**: Check worker is running
```
Dashboard → product-importer-worker → Should show "Running ✓"
```

**Step 2**: Check worker logs
```
Dashboard → product-importer-worker → Logs

Should see:
[INFO/MainProcess] celery@... ready
```

**Step 3**: Check Redis connection
```
Dashboard → product-importer-redis → Should show "Available ✓"
```

**Step 4**: Verify disk is mounted
```
Dashboard → product-importer-web → Settings → Disks
Should show: product-uploads mounted at /data
```

---

## Problem 3: Products Not Appearing After Upload

### Symptoms:
- Upload completes successfully
- Status shows COMPLETED
- But products are not in database

### Solution:

**Step 1**: Check worker logs for errors
```
Dashboard → product-importer-worker → Logs

Look for:
ERROR: Database constraint violation
ERROR: Invalid CSV format
```

**Step 2**: Verify database connection
```
Dashboard → product-importer-db → Info

Should show:
Status: Available
```

**Step 3**: Check product service logs
```
Dashboard → product-importer-worker → Logs

Look for:
"Import completed: X rows processed"
```

**Step 4**: Query database directly
```bash
curl https://product-importer-web-XXXXX.onrender.com/products
```

---

## Problem 4: Slow Performance

### Symptoms:
- First request takes 30-60 seconds
- Service seems unresponsive

### Explanation:
This is **NORMAL** on free tier.

**What's happening**:
1. Service has been idle for >15 minutes
2. Render spins down the service to save resources
3. First request wakes it up (cold start)
4. Subsequent requests are fast

**Solutions**:

**Option 1**: Wait it out (free)
- Accept 30-60 second first load
- Users will experience fast performance after

**Option 2**: Keep-alive pinger (free)
- Set up UptimeRobot or similar
- Ping your site every 10 minutes
- Keeps service awake

**Option 3**: Upgrade to paid plan ($7/month)
- No spin-down
- Always ready
- Professional experience

---

## Problem 5: Worker Not Processing Tasks

### Symptoms:
- Upload succeeds
- Task stuck in QUEUED status
- Never moves to PROCESSING

### Solution:

**Step 1**: Check worker status
```
Dashboard → product-importer-worker → Status should be "Running"
```

**Step 2**: Check worker logs
```
Dashboard → product-importer-worker → Logs

Should see:
[INFO] Connected to redis://...
[INFO] celery@... ready
```

**Step 3**: Check Redis
```
Dashboard → product-importer-redis → Status should be "Available"
```

**Step 4**: Restart worker
```
Dashboard → product-importer-worker → Manual Deploy → Deploy Latest Commit
```

**Step 5**: Check environment variables
```
Dashboard → product-importer-worker → Environment

Should have:
POSTGRES_URL: postgres://...
REDIS_URL: redis://...
CELERY_CONCURRENCY: 2
CELERY_LOG_LEVEL: info
```

---

# PART 6: Updating Your Deployment

## Making Changes and Redeploying

### Step 1: Make Changes Locally

```bash
cd /Users/vedpawar/ai/product-importer

# Edit files
nano app/main.py

# Test locally
docker-compose up
```

### Step 2: Commit Changes

```bash
git add .
git commit -m "Your change description"
```

### Step 3: Push to GitHub

```bash
git push origin main
```

### Step 4: Automatic Redeployment

**Render automatically**:
1. Detects the push to GitHub
2. Triggers a new build
3. Rebuilds Docker images
4. Deploys with zero-downtime
5. Runs health checks
6. Switches traffic to new version

**You'll see in dashboard**:
```
product-importer-web: Deploying...
→ Build complete
→ Deploying new version
→ Health check passed
→ Deploy live ✓
```

**Time**: 5-7 minutes per service

---

# PART 7: Monitoring & Maintenance

## Viewing Logs

### Real-time Logs

```
Dashboard → [Select Service] → Logs tab
```

**Features**:
- Auto-refresh
- Search/filter
- Download logs

### Log Retention

Free tier: 7 days of logs

## Resource Usage

### Check Usage

```
Dashboard → [Select Service] → Metrics tab
```

**You'll see**:
- CPU usage
- Memory usage
- Request count
- Response times

### Set Alerts

```
Dashboard → [Select Service] → Settings → Alerts
```

**Options**:
- Email when service goes down
- Email when deploy fails
- Slack integration (paid plans)

## Database Backups

### Manual Backup

```
Dashboard → product-importer-db → Backups → Create Backup
```

**Free tier**: Manual backups only
**Paid tier**: Automatic daily backups

---

# PART 8: Cost Management

## Current Setup (Free Tier)

| Service | Cost |
|---------|------|
| Web Service | $0/month |
| Worker Service | $0/month |
| PostgreSQL | $0/month |
| Redis | $0/month |
| **Total** | **$0/month** |

## When to Upgrade

Consider upgrading when:

1. **You get real users** (>100/day)
2. **Spin-down is annoying** (30-60s first load)
3. **You need reliability** (business/production use)
4. **You process large files** (>10k rows)
5. **You need more resources** (RAM/CPU limits)

## Upgrade Path

### Starter Plan ($7/month per service)

| Service | Free | Starter |
|---------|------|---------|
| Web | 512 MB RAM | 2 GB RAM |
| Worker | 512 MB RAM | 2 GB RAM |
| Spin-down | Yes (15 min) | No |
| Build minutes | 400/month | 1000/month |

**Total cost**: $28/month (4 services × $7)

### When to Upgrade Each Service

**Upgrade web first**: Eliminates spin-down for users  
**Upgrade worker second**: Better CSV processing  
**Upgrade database third**: More storage (10 GB)  
**Upgrade Redis last**: Usually fine on free tier  

---

# PART 9: Next Steps

## ✅ You're Done!

Your application is now live at:
```
https://product-importer-web-XXXXX.onrender.com
```

## Share Your Application

Send users this URL:
- They can upload CSV files
- View/manage products
- Everything works exactly like local

## Enhance Your Deployment

### Add Custom Domain (Paid Plan)

```
Dashboard → product-importer-web → Settings → Custom Domain
Add: myapp.com
```

### Add Authentication

Consider adding:
- API key authentication
- OAuth2
- JWT tokens

### Add Monitoring

Free tools:
- **UptimeRobot**: Uptime monitoring
- **Sentry**: Error tracking
- **Google Analytics**: Usage tracking

### Improve Performance

```yaml
# In render.yaml, increase resources (requires paid plan)
plan: starter  # Change from: free

envVars:
  - key: UVICORN_WORKERS
    value: 4  # Increase from 1
  - key: CELERY_CONCURRENCY
    value: 8  # Increase from 2
```

---

# PART 10: Quick Reference

## Important URLs

```
Dashboard:    https://dashboard.render.com
Your App:     https://product-importer-web-XXXXX.onrender.com
API Docs:     https://product-importer-web-XXXXX.onrender.com/docs
Health:       https://product-importer-web-XXXXX.onrender.com/health
Products:     https://product-importer-web-XXXXX.onrender.com/products
Frontend:     https://product-importer-web-XXXXX.onrender.com/
```

## Common Commands

```bash
# Push changes
git add .
git commit -m "message"
git push

# Test health
curl https://your-app.onrender.com/health

# Upload CSV
curl -X POST https://your-app.onrender.com/upload/start \
  -F "file=@test.csv"

# Check status
curl https://your-app.onrender.com/upload/status/TASK_ID

# List products
curl https://your-app.onrender.com/products
```

## Service Status

All should show green ✓:
- product-importer-web: Live
- product-importer-worker: Running
- product-importer-db: Available
- product-importer-redis: Available

---

# ✅ Deployment Complete!

**Congratulations!** 🎉

You've successfully deployed a full-stack application with:
- FastAPI backend
- Celery workers
- PostgreSQL database
- Redis cache
- Frontend UI
- File uploads
- Background processing

**Your app is live and ready to use!**

---

## Need Help?

- **Render Docs**: https://render.com/docs
- **Project README**: See README.md
- **Render Status**: https://status.render.com
- **Render Community**: https://community.render.com

---

**Happy deploying!** 🚀

