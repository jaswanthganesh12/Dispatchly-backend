
import asyncio
import logging

from app.core.config import get_settings
from app.infrastructure.streams.client import create_redis_client
from app.infrastructure.workers.consumer import EmailWorker
from app.infrastructure.workers.provider import FakeEmailProvider
from app.infrastructure.workers.resend import ResendEmailProvider


async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    settings = get_settings()

    redis = create_redis_client()
    provider = None

    try:
        if settings.EMAIL_PROVIDER.lower() == "resend":
            provider = ResendEmailProvider()
        elif settings.EMAIL_PROVIDER.lower() == "fake":
            provider = FakeEmailProvider()
        else:
            raise ValueError(
                f"Unsupported email provider: {settings.EMAIL_PROVIDER}"
            )

        worker = EmailWorker(
            redis=redis,
            provider=provider,
        )

        await worker.run_forever()

    finally:
        if provider is not None:
            await provider.close()

        await redis.aclose()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Dispatchly worker stopped.")

