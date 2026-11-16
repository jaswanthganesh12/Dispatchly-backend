
from redis.asyncio import Redis

from app.infrastructure.streams.constants import get_stream_for_priority


async def publish_email_event(
    redis: Redis,
    *,
    outbox_event_id: str,
    email_id: str,
    tenant_id: str,
    priority: int,
) -> str:
    stream = get_stream_for_priority(priority)

    message_id = await redis.xadd(
        stream,
        {
            "outbox_event_id": outbox_event_id,
            "email_id": email_id,
            "tenant_id": tenant_id,
            "priority": str(priority),
            "event_type": "email.queued",
        },
    )

    return message_id

from redis.asyncio import Redis

from app.infrastructure.streams.constants import get_stream_for_priority


async def publish_email_event(
    redis: Redis,
    *,
    outbox_event_id: str,
    email_id: str,
    tenant_id: str,
    priority: int,
) -> str:
    stream = get_stream_for_priority(priority)

    message_id = await redis.xadd(
        stream,
        {
            "outbox_event_id": outbox_event_id,
            "email_id": email_id,
            "tenant_id": tenant_id,
            "priority": str(priority),
            "event_type": "email.queued",
        },
    )

    return message_id
