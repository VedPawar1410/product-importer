from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .api.upload_router import router as upload_router
from .api.product_router import router as product_router
from .api.webhook_router import router as webhook_router

from .core.database import Base, engine
from .models import product, webhook  # import all models so metadata loads

Base.metadata.create_all(bind=engine)


app = FastAPI(title="Product Importer API")

# Include API routers BEFORE static files
app.include_router(upload_router)
app.include_router(product_router)
app.include_router(webhook_router)


@app.get("/health")
async def health_check():
    return {"status": "ok"}


@app.get("/debug/config")
async def debug_config():
    """Debug endpoint to check configuration"""
    from .core.config import settings
    import os
    
    return {
        "database_url_set": bool(settings.database_url),
        "database_url_prefix": settings.database_url[:20] if settings.database_url else None,
        "celery_broker_url_set": bool(settings.celery_broker_url),
        "celery_broker_url_prefix": settings.celery_broker_url[:20] if settings.celery_broker_url else None,
        "env_vars": {
            "DATABASE_URL": bool(os.getenv("DATABASE_URL")),
            "POSTGRES_URL": bool(os.getenv("POSTGRES_URL")),
            "REDIS_URL": bool(os.getenv("REDIS_URL")),
            "CELERY_BROKER_URL": bool(os.getenv("CELERY_BROKER_URL")),
            "PORT": os.getenv("PORT", "not set"),
        }
    }


@app.get("/debug/redis")
async def debug_redis():
    """Test Redis connection"""
    from .core.config import settings
    from redis import Redis
    
    try:
        redis_client = Redis.from_url(settings.celery_broker_url, decode_responses=True)
        redis_client.ping()
        return {"status": "ok", "message": "Redis connection successful"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# -------------------------------
# STATIC FRONTEND CONFIG
# -------------------------------
# IMPORTANT: Mount static files LAST so API routes take precedence
frontend_dir = Path(__file__).parent.parent / "frontend"

# This serves:
# /           → index.html
# /index.html → index.html
# /products.html → loads file
# /webhooks.html → loads file
# But API routes (/products, /upload, /webhooks) are handled first
app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
