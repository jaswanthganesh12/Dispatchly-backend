
from typing import Annotated
import hashlib
import json

from fastapi import Header
from sqlalchemy import func
from app.db.models import IdempotencyRecord

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.dependencies import get_db_session
from app.db.models import Email, OutboxEvent, Tenant
from app.schemas.email import EmailCreate, EmailResponse


router = APIRouter(
    prefix="/v1/emails",
    tags=["Emails"],
)



@router.post(
    "",
    response_model=EmailResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def submit_email(
    email_data: EmailCreate,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    idempotency_key: Annotated[
        str,
        Header(
            alias="Idempotency-Key",
            min_length=1,
            max_length=255,
        ),
    ],
):
    idempotency_key = idempotency_key.strip()

    if not idempotency_key:
        raise HTTPException(
            status_code=400,
            detail="Idempotency-Key cannot be empty",
        )

  
    payload = email_data.model_dump(mode="json")

    serialized_payload = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    )

    request_hash = hashlib.sha256(
        serialized_payload.encode("utf-8")
    ).hexdigest()

    email_to_return = None

    async with db.begin():

       
        tenant = await db.scalar(
            select(Tenant).where(
                Tenant.id == email_data.tenant_id
            )
        )

        if tenant is None:
            raise HTTPException(
                status_code=404,
                detail="Tenant not found",
            )

        if not tenant.is_active:
            raise HTTPException(
                status_code=403,
                detail="Tenant is inactive",
            )

       
        lock_key = f"{tenant.id}:{idempotency_key}"

        await db.execute(
            select(
                func.pg_advisory_xact_lock(
                    func.hashtextextended(lock_key, 0)
                )
            )
        )

        existing_record = await db.scalar(
            select(IdempotencyRecord).where(
                IdempotencyRecord.tenant_id == tenant.id,
                IdempotencyRecord.idempotency_key
                == idempotency_key,
            )
        )

        if existing_record is not None:

            if existing_record.request_hash != request_hash:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "Idempotency key already used "
                        "with a different request payload"
                    ),
                )

            email_to_return = await db.get(
                Email,
                existing_record.email_id,
            )

        else:
            email = Email(
                tenant_id=tenant.id,
                recipient_email=str(email_data.recipient_email),
                sender_email=str(email_data.sender_email),
                subject=email_data.subject,
                html_body=email_data.html_body,
                text_body=email_data.text_body,
                priority=email_data.priority,
                scheduled_at=email_data.scheduled_at,
            )

            db.add(email)
            await db.flush()
            event = OutboxEvent(
                aggregate_type="email",
                aggregate_id=email.id,
                event_type="email.queued",
                payload={
                    "email_id": str(email.id),
                    "tenant_id": str(tenant.id),
                },
            )

            if email.scheduled_at is not None:
                event.available_at = email.scheduled_at

            db.add(event)

            idempotency_record = IdempotencyRecord(
                tenant_id=tenant.id,
                idempotency_key=idempotency_key,
                request_hash=request_hash,
                email_id=email.id,
            )

            db.add(idempotency_record)

            email_to_return = email

    await db.refresh(email_to_return)

    return email_to_return

