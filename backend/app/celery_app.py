"""
Celery application configuration.
"""
from celery import Celery
from app.config import settings

celery = Celery(
    "ocr_system",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "app.tasks.document_tasks",
        "app.tasks.batch_tasks",
    ],
)

celery.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_routes={
        "app.tasks.document_tasks.*": {"queue": "documents"},
        "app.tasks.batch_tasks.*": {"queue": "batches"},
    },
    task_max_retries=3,
    task_default_retry_delay=60,  # seconds
    result_expires=86400 * 7,  # 7 days
)
