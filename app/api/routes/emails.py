
from typing import Annotated

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
):
    async with db.begin():
      
        result = await db.execute(
            select(Tenant).where(
                Tenant.id == email_data.tenant_id
            )
        )

        tenant = result.scalar_one_or_none()

        if tenant is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tenant not found",
            )

        if not tenant.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Tenant is inactive",
            )


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

 
    await db.refresh(email)

    return email
