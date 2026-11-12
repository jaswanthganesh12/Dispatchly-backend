
from datetime import timedelta
from uuid import uuid4

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
