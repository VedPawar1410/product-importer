from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from .api.upload_router import router as upload_router
from .api.product_router import router as product_router
from .api.webhook_router import router as webhook_router

app = FastAPI(title="Product Importer API")

# Include API routers
app.include_router(upload_router)
app.include_router(product_router)
app.include_router(webhook_router)


@app.get("/health")
async def health_check():
    return {"status": "ok"}


@app.get("/")
async def read_root():
    return FileResponse("frontend/index.html")


# Mount static files (must be last to avoid conflicting with API routes)
frontend_dir = Path(__file__).parent.parent / "frontend"
app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
