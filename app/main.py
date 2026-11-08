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
