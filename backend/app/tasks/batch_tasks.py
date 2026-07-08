"""
Batch-level Celery tasks.
"""
import logging
import uuid
from datetime import datetime

from app.celery_app import celery
from app.tasks.document_tasks import _update_batch_counts

logger = logging.getLogger(__name__)


@celery.task(
    name="app.tasks.batch_tasks.finalize_batch",
    queue="batches",
)
def finalize_batch(batch_id: str):
    """
    Finalize batch status after all documents complete.
    Called as a chord callback or manually.
    """
    logger.info(f"Finalizing batch {batch_id}")
    _update_batch_counts(batch_id)
    return {"status": "finalized", "batch_id": batch_id}
