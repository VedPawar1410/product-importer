from celery import Celery

from .config import settings

celery_app = Celery(
    "product_importer",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)


@celery_app.task
def example_task() -> str:
    """A placeholder Celery task."""
    # TODO: Replace with real task implementation
    return "example"
