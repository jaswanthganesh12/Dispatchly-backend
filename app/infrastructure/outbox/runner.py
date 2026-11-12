
import asyncio
import logging

from app.infrastructure.outbox.dispatcher import (
    claim_pending_events,
    publish_claimed_events,
)

logger = logging.getLogger(__name__)


async def run_dispatcher_once() -> dict[str, int]:
    events = await claim_pending_events(batch_size=100)

    if not events:
        return {
            "claimed": 0,
            "published": 0,
            "failed": 0,
        }

    result = await publish_claimed_events(events)

    return {
        "claimed": len(events),
        **result,
    }


async def run_forever(poll_interval: int = 2):
    logger.info("Dispatchly outbox dispatcher started")

    while True:
        try:
            result = await run_dispatcher_once()

            if result["claimed"] > 0:
                logger.info(
                    "Dispatcher cycle completed",
                    extra=result,
                )

        except Exception:
            logger.exception("Dispatcher cycle failed")

        await asyncio.sleep(poll_interval)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_forever())
