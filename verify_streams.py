
import asyncio

from app.infrastructure.streams.client import create_redis_client
from app.infrastructure.streams.consumer import initialize_consumer_groups


async def main():
    redis = create_redis_client()

    try:
        await initialize_consumer_groups(redis)

        print("\n--- STREAM GROUP VERIFICATION ---")

        streams = [
            "dispatchly:emails:critical",
            "dispatchly:emails:normal",
            "dispatchly:emails:bulk",
        ]

        for stream in streams:
            groups = await redis.xinfo_groups(stream)
            print(f"\n{stream}")

            for group in groups:
                print(f"  Group: {group['name']}")
                print(f"  Consumers: {group['consumers']}")
                print(f"  Pending: {group['pending']}")

    finally:
        await redis.aclose()


asyncio.run(main())
