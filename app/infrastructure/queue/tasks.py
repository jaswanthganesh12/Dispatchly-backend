
import asyncio
import logging

from app.infrastructure.queue.celery_app import celery_app
from app.infrastructure.queue.processor import process_email_record

logger = logging.getLogger(__name__)


@celery_app.task(
    name="dispatchly.process_email",
    bind=True,
    max_retries=5,
)
def process_email(self, email_id: str):
    logger.info(
        "Starting email processing",
        extra={"email_id": email_id},
    )

    result = asyncio.run(process_email_record(email_id))

    logger.info(
        "Email processing result",
        extra=result,
    )

    return result




