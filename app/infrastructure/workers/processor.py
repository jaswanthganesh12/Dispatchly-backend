
from datetime import timedelta
from uuid import UUID, uuid4

from sqlalchemy import func, select

from app.db.models import Email, EmailAttempt, OutboxEvent
from app.db.session import AsyncSessionLocal
from app.infrastructure.workers.provider import (
    EmailProvider,
    ProviderResult,
)


async def process_email(
    email_id: str,
    provider: EmailProvider,
) -> dict:
    email_uuid = UUID(email_id)
    attempt_id = uuid4()

  
    async with AsyncSessionLocal() as session:
        async with session.begin():
            email = await session.scalar(
                select(Email)
                .where(Email.id == email_uuid)
                .with_for_update()
            )

            if email is None:
                return {"status": "NOT_FOUND"}

           
            if email.status not in ("QUEUED", "RETRY"):
                return {
                    "status": "SKIPPED",
                    "email_status": email.status,
                }

            if email.attempts >= email.max_attempts:
                email.status = "FAILED"
                return {"status": "MAX_ATTEMPTS_REACHED"}

            email.attempts += 1
            email.status = "PROCESSING"

            attempt_number = email.attempts

            attempt = EmailAttempt(
                id=attempt_id,
                email_id=email.id,
                attempt_number=attempt_number,
                provider_name=provider.provider_name,
                status="STARTED",
            )

            session.add(attempt)

   
            email_data = {
                "recipient": email.recipient_email,
                "sender": email.sender_email,
                "subject": email.subject,
                "html_body": email.html_body,
                "text_body": email.text_body,
                "priority": email.priority,
                "max_attempts": email.max_attempts,
            }

  
    try:
        provider_result = await provider.send(
            recipient=email_data["recipient"],
            sender=email_data["sender"],
            subject=email_data["subject"],
            html_body=email_data["html_body"],
            text_body=email_data["text_body"],
            idempotency_key=f"dispatchly-email-{email_id}",
        )

    except Exception as exc:
        provider_result = ProviderResult(
            success=False,
            provider_name=provider.provider_name,
            error_code="PROVIDER_EXCEPTION",
            error_message=str(exc)[:2000],
            retryable=True,
        )

   
    async with AsyncSessionLocal() as session:
        async with session.begin():
            email = await session.scalar(
                select(Email)
                .where(Email.id == email_uuid)
                .with_for_update()
            )

            attempt = await session.scalar(
                select(EmailAttempt).where(
                    EmailAttempt.id == attempt_id
                )
            )

            if email is None or attempt is None:
                raise RuntimeError(
                    "Email or attempt record disappeared"
                )

            attempt.completed_at = await session.scalar(
                select(func.now())
            )

            if provider_result.success:
                attempt.status = "SUCCESS"
                attempt.provider_message_id = (
                    provider_result.provider_message_id
                )

                email.status = "SUBMITTED"

                return {
                    "status": "SUBMITTED",
                    "attempt_number": attempt.attempt_number,
                    "provider_message_id": (
                        provider_result.provider_message_id
                    ),
                }

            attempt.status = "FAILED"
            attempt.error_code = provider_result.error_code
            attempt.error_message = provider_result.error_message

            if (
                provider_result.retryable
                and email.attempts < email.max_attempts
            ):
                email.status = "RETRY"

                delay = min(
                    2 ** email.attempts,
                    300,
                )

                retry_event = OutboxEvent(
                    aggregate_type="email",
                    aggregate_id=email.id,
                    event_type="email.queued",
                    payload={
                        "email_id": str(email.id),
                        "tenant_id": str(email.tenant_id),
                        "priority": email.priority,
                    },
                    available_at=(
                        await session.scalar(select(func.now()))
                        + timedelta(seconds=delay)
                    ),
                )

                session.add(retry_event)

                return {
                    "status": "RETRY",
                    "attempt_number": email.attempts,
                    "retry_in_seconds": delay,
                }

            email.status = "FAILED"

            return {
                "status": "FAILED",
                "attempt_number": email.attempts,
                "error": provider_result.error_message,
            }
