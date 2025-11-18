from pydantic import BaseSettings


class Settings(BaseSettings):
    """Application configuration pulled from environment variables or defaults."""

    database_url: str = "sqlite:///./app.db"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/0"

    class Config:
        env_file = ".env"


settings = Settings()
