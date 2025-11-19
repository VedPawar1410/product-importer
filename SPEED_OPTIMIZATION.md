# ⚡ CSV Upload Speed Optimization Guide

## 🐌 Common Slow Upload Causes on Render Free Tier

### 1. **Cold Start (Most Common)**
**Symptom:** First upload after 15 min is very slow (30-60 seconds)
**Cause:** Service was asleep and needs to wake up
**Solution:** This is normal on free tier - subsequent uploads are fast

### 2. **Large File Size**
**Symptom:** Upload progress bar moves slowly
**Cause:** Free tier has limited bandwidth and slow Redis writes
**Solution:** See optimizations below

### 3. **Redis Storage**
**Symptom:** Upload bar reaches 100% but hangs before "Processing"
**Cause:** Writing entire file to Redis takes time
**Solution:** See optimizations below

---

## ⚡ Quick Fixes (Apply Now)

### Fix 1: Add File Size Limit (Frontend)

**File:** `frontend/app.js`

Add this check in `uploadCSVFile()` function after line 50:

```javascript
// Add file size check (5 MB limit for free tier)
const maxSize = 5 * 1024 * 1024; // 5 MB
if (file.size > maxSize) {
    setStatus('error', `File too large (${(file.size / 1024 / 1024).toFixed(1)} MB). Maximum: 5 MB on free tier.`);
    resetUploadButton();
    return;
}

// Show file size to user
console.log(`Uploading file: ${file.name} (${(file.size / 1024).toFixed(1)} KB)`);
```

### Fix 2: Add Better Upload Feedback

**File:** `frontend/app.js`

Update the `uploadCSVFile()` function to show size info:

```javascript
// After line 54 (uploadBtn.textContent = 'Uploading...';)
const fileSizeKB = (file.size / 1024).toFixed(1);
uploadBtn.textContent = `Uploading ${fileSizeKB} KB...`;
```

### Fix 3: Optimize Redis Connection Pooling

**File:** `app/api/upload_router.py`

Add connection pooling at the top:

```python
from redis.connection import ConnectionPool

# Create connection pool (reuse connections)
_redis_pool = None

def get_redis_client(decode_responses=True):
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = ConnectionPool.from_url(
            settings.celery_broker_url,
            max_connections=10,
            decode_responses=False
        )
    return Redis(connection_pool=_redis_pool, decode_responses=decode_responses)
```

Then replace lines 50-51 with:
```python
redis_client_binary = get_redis_client(decode_responses=False)
```

And line 55 with:
```python
redis_client = get_redis_client(decode_responses=True)
```

---

## 🎯 Recommended File Sizes for Free Tier

| File Size | Upload Time | Processing Time | Status |
|-----------|-------------|-----------------|--------|
| < 100 KB | 1-2 sec | 2-5 sec | ✅ Excellent |
| 100 KB - 500 KB | 2-5 sec | 5-15 sec | ✅ Good |
| 500 KB - 1 MB | 5-10 sec | 15-30 sec | ✅ Acceptable |
| 1 MB - 5 MB | 10-30 sec | 30-120 sec | ⚠️ Slow |
| > 5 MB | 30+ sec | 2+ min | ❌ Too slow |

**Recommendation:** Keep test files under 1 MB for best experience on free tier.

---

## 🔍 Diagnose Your Specific Issue

### Test 1: Check File Size

```bash
# Create a small test file (10 rows = ~1 KB)
cat > test-small.csv << 'EOF'
sku,name,description,price,active
TEST001,Product 1,Description 1,19.99,true
TEST002,Product 2,Description 2,29.99,true
TEST003,Product 3,Description 3,39.99,false
TEST004,Product 4,Description 4,49.99,true
TEST005,Product 5,Description 5,59.99,true
TEST006,Product 6,Description 6,69.99,false
TEST007,Product 7,Description 7,79.99,true
TEST008,Product 8,Description 8,89.99,true
TEST009,Product 9,Description 9,99.99,false
TEST010,Product 10,Description 10,19.99,true
EOF

# Check size
ls -lh test-small.csv
# Should show: ~500 bytes

# Upload this - should be fast (< 5 seconds total)
```

If this is fast, your issue is file size.

### Test 2: Check Cold Start

```bash
# Wait 15 minutes after last request
# Then try uploading

# First upload: 30-60 seconds (normal - cold start)
# Second upload (immediate): < 5 seconds (normal - warm)
```

If second upload is fast, issue is cold start (normal for free tier).

### Test 3: Check Redis Performance

Open browser console (F12) and look at network tab:
- `POST /upload/start` request time
- If > 10 seconds for small file (< 1 MB), Redis is slow

---

## 🚀 Advanced Optimizations

### Option 1: Compress File Before Upload

**File:** `frontend/app.js`

Add compression (requires pako.js library):

```html
<!-- Add to index.html before app.js -->
<script src="https://cdnjs.cloudflare.com/ajax/libs/pako/2.1.0/pako.min.js"></script>
```

```javascript
// In uploadCSVFile() function
const reader = new FileReader();
reader.onload = function(e) {
    const compressed = pako.gzip(e.target.result);
    formData.append('file', new Blob([compressed]), file.name + '.gz');
    // Continue with xhr.send(formData)
};
reader.readAsArrayBuffer(file);
```

**Reduction:** ~60-80% smaller uploads

### Option 2: Chunked Upload

For large files, split into chunks:

```javascript
async function uploadLargeFile(file) {
    const chunkSize = 100 * 1024; // 100 KB chunks
    const chunks = Math.ceil(file.size / chunkSize);
    
    for (let i = 0; i < chunks; i++) {
        const start = i * chunkSize;
        const end = Math.min(start + chunkSize, file.size);
        const chunk = file.slice(start, end);
        
        const formData = new FormData();
        formData.append('chunk', chunk);
        formData.append('chunkIndex', i);
        formData.append('totalChunks', chunks);
        
        await fetch('/upload/chunk', {
            method: 'POST',
            body: formData
        });
        
        updateProgress((i + 1) / chunks * 100);
    }
}
```

**Benefit:** Better progress tracking, less memory usage

### Option 3: Direct Streaming (Backend)

**File:** `app/api/upload_router.py`

Process CSV without storing entirely in Redis:

```python
@router.post("/start-streaming")
async def start_upload_streaming(file: UploadFile = File(...)):
    """Stream CSV directly to processing without Redis storage"""
    task_id = uuid.uuid4().hex
    
    # Read and process in chunks
    chunk_size = 8192
    lines = []
    buffer = b""
    
    while chunk := await file.read(chunk_size):
        buffer += chunk
        # Process complete lines immediately
        while b'\n' in buffer:
            line, buffer = buffer.split(b'\n', 1)
            lines.append(line.decode('utf-8'))
            
            # Process batch
            if len(lines) >= 100:
                # Process these 100 rows immediately
                process_batch(lines)
                lines = []
    
    return {"task_id": task_id}
```

**Benefit:** No Redis storage delay, immediate processing

---

## 🎯 Immediate Action Plan

### For Your Current Deployment:

**1. Test with Small File First**

```bash
# Create 10-row test file
cat > test-quick.csv << 'EOF'
sku,name,description,price,active
Q001,Quick Test 1,Test,9.99,true
Q002,Quick Test 2,Test,9.99,true
Q003,Quick Test 3,Test,9.99,true
Q004,Quick Test 4,Test,9.99,true
Q005,Quick Test 5,Test,9.99,true
Q006,Quick Test 6,Test,9.99,true
Q007,Quick Test 7,Test,9.99,true
Q008,Quick Test 8,Test,9.99,true
Q009,Quick Test 9,Test,9.99,true
Q010,Quick Test 10,Test,9.99,true
EOF
```

Upload this file. Should complete in < 10 seconds total.

**2. If Still Slow, Check:**

```bash
# In browser console (F12 → Network tab)
# Look at the /upload/start request
# Check: Time, Status, Response

# In Render Dashboard
# Go to: product-importer-web → Logs
# Look for: Any errors, Redis connection issues
```

**3. Add Frontend File Size Warning**

Add to `index.html` after file input:

```html
<p class="text-sm text-gray-600 mt-2">
    💡 Tip: For fastest uploads on free tier, use files under 1 MB
</p>
```

---

## 📊 Expected Performance (Free Tier)

### Normal Speeds:

| Scenario | Time | Normal? |
|----------|------|---------|
| **Cold start (first request)** | 30-60 sec | ✅ Yes |
| **Small file (< 100 KB)** | 3-8 sec | ✅ Yes |
| **Medium file (500 KB)** | 8-20 sec | ✅ Yes |
| **Large file (2 MB)** | 20-45 sec | ⚠️ Slow but normal |
| **Huge file (10 MB)** | 1-3 min | ❌ Too slow |

### If Slower Than This:

1. **Check Render Logs** for errors
2. **Verify Redis is connected** (env vars correct)
3. **Test with tiny file** (10 rows) to isolate issue
4. **Check if Celery worker started** (logs should show "ready")

---

## 💡 Tell Your Client

```
Note: This deployment uses Render's free tier which has:
• Service cold-start: first request takes 30-60 seconds
• Limited resources: best with files under 1 MB
• Shared infrastructure: processing may be slower than local

For production use with larger files, a paid plan ($7/month) 
provides 4x more resources and no cold-start delays.
```

---

## 🔧 Quick Debug Commands

```bash
# Check if service is sleeping
curl https://YOUR-APP.onrender.com/health
# If > 30 sec, it was sleeping

# Test upload with tiny file via API
curl -X POST https://YOUR-APP.onrender.com/upload/start \
  -F "file=@test-quick.csv"
# Should return task_id in < 5 seconds

# Check Redis connection
# (In Render Dashboard logs, should see):
# "Connected to redis://..."
```

---

## ✅ Summary

**Most likely cause:** Cold start or large file on free tier

**Quick fix:** 
1. Test with small file (< 100 KB)
2. Expect 30-60 sec first upload (cold start)
3. Subsequent uploads should be < 10 sec

**Long-term fix:**
1. Add file size limits (5 MB max)
2. Add frontend size warning
3. Consider paid plan for production ($7/month)

---

**Need help debugging?** Share:
1. File size you're testing
2. Time for upload progress bar (0% → 100%)
3. Time after 100% before "Processing" appears
4. Any errors in browser console (F12)

