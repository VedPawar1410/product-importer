import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8",
        extra="ignore"  # Ignore extra environment variables
    )
    
    # Support both Render's POSTGRES_URL and legacy DATABASE_URL
    database_url: str = os.getenv("POSTGRES_URL") or os.getenv("DATABASE_URL") or "postgresql://postgres:postgres@db:5432/products"
    
    # Support both Render's REDIS_URL and legacy CELERY_BROKER_URL
    celery_broker_url: str = os.getenv("REDIS_URL") or os.getenv("CELERY_BROKER_URL") or "redis://redis:6379/0"
    celery_result_backend: str = os.getenv("REDIS_URL") or os.getenv("CELERY_RESULT_BACKEND") or "redis://redis:6379/0"

settings = Settings()
