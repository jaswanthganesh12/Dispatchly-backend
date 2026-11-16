
from redis.asyncio import Redis
from redis.exceptions import ResponseError

from app.infrastructure.streams.constants import (
    BULK_STREAM,
    CONSUMER_GROUP,
    CRITICAL_STREAM,
    NORMAL_STREAM,
)


STREAMS = [
    CRITICAL_STREAM,
    NORMAL_STREAM,
    BULK_STREAM,
]


async def initialize_consumer_groups(redis: Redis) -> None:
    for stream in STREAMS:
        try:
            await redis.xgroup_create(
                name=stream,
                groupname=CONSUMER_GROUP,
                id="0-0",
                mkstream=True,
            )
            print(f"Created consumer group for {stream}")

        except ResponseError as exc:
            if "BUSYGROUP" in str(exc):
                print(f"Consumer group already exists for {stream}")
            else:
                raise
