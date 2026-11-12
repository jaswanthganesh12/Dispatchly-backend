
import logging

from app.infrastructure.queue.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name="dispatchly.process_email",
    bind=True,
    max_retries=5,
)
def process_email(self, email_id: str):
    logger.info(
        "Received email processing task",
        extra={"email_id": email_id},
    )


    return {
        "email_id": email_id,
        "status": "RECEIVED",
    }
