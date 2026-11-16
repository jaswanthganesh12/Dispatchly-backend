
import asyncio
from uuid import uuid4

from app.infrastructure.streams.client import create_redis_client
from app.infrastructure.streams.publisher import publish_email_event


async def main():
    redis = create_redis_client()

    try:
        test_cases = [
            (9, "CRITICAL"),
            (5, "NORMAL"),
            (2, "BULK"),
        ]

        for priority, category in test_cases:
            message_id = await publish_email_event(
                redis,
                outbox_event_id=str(uuid4()),
                email_id=str(uuid4()),
                tenant_id=str(uuid4()),
                priority=priority,
            )

            print(f"{category}: priority={priority}, message_id={message_id}")

    finally:
        await redis.aclose()


asyncio.run(main())
