
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from svix.webhooks import Webhook, WebhookVerificationError

from app.core.config import get_settings
from app.db.dependencies import get_db_session
from app.db.models.email import Email
from app.db.models.email_attempt import EmailAttempt
from app.db.models.webhook_event import WebhookEvent


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])
settings = get_settings()


EVENT_STATUS_MAP = {
    "email.delivered": "DELIVERED",
    "email.bounced": "BOUNCED",
    "email.complained": "COMPLAINED",
}

STATUS_RANK = {
    "SUBMITTED": 0,
    "DELIVERED": 1,
    "BOUNCED": 2,
    "COMPLAINED": 3,
}


@router.post("/resend", status_code=204)
async def handle_resend_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db_session),
):
    if not settings.RESEND_WEBHOOK_SECRET:
        raise HTTPException(
            status_code=500,
            detail="Webhook signing secret is not configured",
        )

    raw_body = await request.body()

    headers = {
        "svix-id": request.headers.get("svix-id"),
        "svix-timestamp": request.headers.get("svix-timestamp"),
        "svix-signature": request.headers.get("svix-signature"),
    }

    if not all(headers.values()):
        raise HTTPException(
            status_code=400,
            detail="Missing Svix signature headers",
        )

   
    try:
        Webhook(settings.RESEND_WEBHOOK_SECRET).verify(
            raw_body.decode("utf-8"),
            headers,
        )

        event = json.loads(raw_body)

    except (
        WebhookVerificationError,
        ValueError,
        UnicodeDecodeError,
    ):
        raise HTTPException(
            status_code=400,
            detail="Invalid webhook signature or payload",
        )

    if not isinstance(event, dict):
        raise HTTPException(
            status_code=400,
            detail="Invalid webhook event payload",
        )

    event_type = event.get("type")
    event_data = event.get("data", {})

    if not isinstance(event_data, dict) or not event_type:
        raise HTTPException(
            status_code=400,
            detail="Invalid webhook event payload",
        )

    provider_email_id = event_data.get("email_id")
    target_status = EVENT_STATUS_MAP.get(event_type)

    try:
        async with db.begin():
           
            statement = (
                insert(WebhookEvent)
                .values(
                    provider_name="resend",
                    provider_event_id=headers["svix-id"],
                    event_type=event_type,
                    provider_email_id=provider_email_id,
                    payload=event,
                    processing_status="RECEIVED",
                )
                .on_conflict_do_nothing(
                    index_elements=["provider_event_id"],
                )
                .returning(WebhookEvent.id)
            )

            result = await db.execute(statement)
            webhook_event_id = result.scalar_one_or_none()

            
            if webhook_event_id is None:
                return Response(status_code=204)

         
            if not target_status or not provider_email_id:
                await db.execute(
                    WebhookEvent.__table__.update()
                    .where(WebhookEvent.id == webhook_event_id)
                    .values(
                        processing_status="PROCESSED",
                        processed_at=datetime.now(timezone.utc),
                    )
                )
                return Response(status_code=204)

         
            email_result = await db.execute(
                select(Email)
                .join(
                    EmailAttempt,
                    EmailAttempt.email_id == Email.id,
                )
                .where(
                    EmailAttempt.provider_message_id == provider_email_id,
                )
                .with_for_update(of=Email)
            )

            email = email_result.scalar_one_or_none()

            if email is None:
                await db.execute(
                    WebhookEvent.__table__.update()
                    .where(WebhookEvent.id == webhook_event_id)
                    .values(
                        processing_status="UNMATCHED",
                        processed_at=datetime.now(timezone.utc),
                    )
                )
                return Response(status_code=204)

            current_rank = STATUS_RANK.get(email.status, -1)
            target_rank = STATUS_RANK[target_status]

            
            if target_rank > current_rank:
                email.status = target_status

            await db.execute(
                WebhookEvent.__table__.update()
                .where(WebhookEvent.id == webhook_event_id)
                .values(
                    processing_status="PROCESSED",
                    processed_at=datetime.now(timezone.utc),
                )
            )

    except Exception:
        logger.exception("Resend webhook processing failed")
        raise

    return Response(status_code=204)


