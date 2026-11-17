
from redis.asyncio import Redis

from app.core.config import get_settings


settings = get_settings()


def create_redis_client() -> Redis:
    """
    Create an asynchronous Redis client
    for Dispatchly Streams.
    """
    return Redis.from_url(
        settings.REDIS_URL,
        decode_responses=True,
        health_check_interval=30,
        socket_connect_timeout=5,
        socket_timeout=15,
    )


async def close_redis_client(client: Redis) -> None:
    """Close the Redis connection pool."""
    await client.aclose()
