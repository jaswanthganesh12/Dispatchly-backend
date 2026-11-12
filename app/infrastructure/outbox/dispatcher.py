
from datetime import timedelta
from uuid import UUID,uuid4
import asyncio

from sqlalchemy import update

from app.infrastructure.queue.celery_app import celery_app

from sqlalchemy import func, or_, select

from app.db.models import OutboxEvent
from app.db.session import AsyncSessionLocal


async def claim_pending_events(
    batch_size: int = 100,
    lease_seconds: int = 60,
) -> list[dict]:
    if batch_size < 1:
        raise ValueError("batch_size must be positive")

    dispatcher_id = str(uuid4())
    claimed_events = []

    async with AsyncSessionLocal() as session:
        async with session.begin():

            
            db_now = await session.scalar(select(func.now()))

            lease_until = db_now + timedelta(
                seconds=lease_seconds
            )

            query = (
                select(OutboxEvent)
                .where(
                    OutboxEvent.published_at.is_(None),
                    OutboxEvent.available_at <= db_now,
                    or_(
                        OutboxEvent.locked_until.is_(None),
                        OutboxEvent.locked_until < db_now,
                    ),
                )
                .order_by(
                    OutboxEvent.available_at,
                    OutboxEvent.created_at,
                )
                .limit(batch_size)
                .with_for_update(skip_locked=True)
            )

            result = await session.execute(query)

            events = result.scalars().all()

            for event in events:
                event.locked_by = dispatcher_id
                event.locked_until = lease_until
                event.attempts += 1

                claimed_events.append({
                    "id": str(event.id),
                    "dispatcher_id": dispatcher_id,
                    "event_type": event.event_type,
                    "payload": event.payload,
                    "attempts": event.attempts,
                })

    return claimed_events


async def publish_claimed_events(
    events: list[dict],
) -> dict[str, int]:

    published = 0
    failed = 0

    for event in events:
        event_id = UUID(event["id"])
        dispatcher_id = event["dispatcher_id"]
        email_id = event["payload"]["email_id"]

        try:
            # Publish the Celery task to Redis.
            await asyncio.to_thread(
                celery_app.send_task,
                "dispatchly.process_email",
                args=[email_id],
                task_id=str(event_id),
            )

            # Mark the event as published only if we still own it.
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    result = await session.execute(
                        update(OutboxEvent)
                        .where(
                            OutboxEvent.id == event_id,
                            OutboxEvent.locked_by == dispatcher_id,
                            OutboxEvent.published_at.is_(None),
                        )
                        .values(
                            published_at=func.now(),
                            locked_by=None,
                            locked_until=None,
                            last_error=None,
                        )
                    )

                    if result.rowcount == 1:
                        published += 1

        except Exception as exc:
            delay = min(2 ** event["attempts"], 300)

            async with AsyncSessionLocal() as session:
                async with session.begin():
                    result = await session.execute(
                        update(OutboxEvent)
                        .where(
                            OutboxEvent.id == event_id,
                            OutboxEvent.locked_by == dispatcher_id,
                            OutboxEvent.published_at.is_(None),
                        )
                        .values(
                            available_at=(
                                func.now()
                                + timedelta(seconds=delay)
                            ),
                            locked_by=None,
                            locked_until=None,
                            last_error=str(exc)[:2000],
                        )
                    )

                    if result.rowcount == 1:
                        failed += 1

    return {
        "published": published,
        "failed": failed,
    }

