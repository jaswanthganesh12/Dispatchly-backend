
import asyncio
import logging
import socket
import uuid

from redis.asyncio import Redis
from redis.exceptions import ResponseError

from app.infrastructure.streams.constants import (
    BULK_STREAM,
    CONSUMER_GROUP,
    CRITICAL_STREAM,
    NORMAL_STREAM,
)
from app.infrastructure.workers.processor import process_email
from app.infrastructure.workers.provider import EmailProvider


logger = logging.getLogger(__name__)

STREAMS = [
    CRITICAL_STREAM,
    NORMAL_STREAM,
    BULK_STREAM,
]


class EmailWorker:

    def __init__(
        self,
        redis: Redis,
        provider: EmailProvider | None = None,
    ):
        self.redis = redis
        self.provider = provider

        self.reclaim_idle_ms = 60_000
        self.reclaim_batch_size = 10

        self.consumer_name = (
            f"{socket.gethostname()}-{uuid.uuid4().hex[:8]}"
        )

    async def initialize(self):
        """Create consumer groups if they do not already exist."""

        for stream in STREAMS:
            try:
                await self.redis.xgroup_create(
                    name=stream,
                    groupname=CONSUMER_GROUP,
                    id="0-0",
                    mkstream=True,
                )

                logger.info("Created consumer group for %s", stream)

            except ResponseError as exc:
                if "BUSYGROUP" not in str(exc):
                    raise

        logger.info(
            "Worker registered: %s",
            self.consumer_name,
        )

    async def recover_pending_messages(self):
        """Reclaim messages abandoned by inactive consumers."""

        for stream in STREAMS:
            try:
                next_id, messages, deleted_ids = (
                    await self.redis.xautoclaim(
                        name=stream,
                        groupname=CONSUMER_GROUP,
                        consumername=self.consumer_name,
                        min_idle_time=self.reclaim_idle_ms,
                        start_id="0-0",
                        count=self.reclaim_batch_size,
                    )
                )

                if deleted_ids:
                    logger.warning(
                        "References to deleted messages in %s: %s",
                        stream,
                        deleted_ids,
                    )

                for message_id, fields in messages:
                    logger.warning(
                        "Recovering abandoned message: %s",
                        message_id,
                    )

                    await self.process_message(
                        stream,
                        message_id,
                        fields,
                    )

                if messages:
                    logger.info(
                        "Reclaimed %s messages from %s",
                        len(messages),
                        stream,
                    )

            except Exception:
                logger.exception(
                    "Failed to recover pending messages from %s",
                    stream,
                )

    async def consume_once(self):
        """Read and process new messages from all priority streams."""

        messages = await self.redis.xreadgroup(
            groupname=CONSUMER_GROUP,
            consumername=self.consumer_name,
            streams={
                stream: ">"
                for stream in STREAMS
            },
            count=10,
            block=5000,
        )

        for stream, entries in messages:
            for message_id, fields in entries:
                await self.process_message(
                    stream,
                    message_id,
                    fields,
                )

    async def process_message(
        self,
        stream: str,
        message_id: str,
        fields: dict,
    ):
        """Process an email and acknowledge the message on normal return."""

        email_id = fields.get("email_id")

        if not email_id:
            logger.error(
                "Message %s has no email_id; leaving pending",
                message_id,
            )
            return

        try:
            result = await process_email(
                email_id=email_id,
                provider=self.provider,
            )

            logger.info(
                "Email processing result",
                extra={
                    "email_id": email_id,
                    "stream": stream,
                    "message_id": message_id,
                    "result": result,
                },
            )

            await self.redis.xack(
                stream,
                CONSUMER_GROUP,
                message_id,
            )

        except Exception:
            logger.exception(
                "Email processing failed; message remains pending: %s",
                message_id,
            )

    async def run_forever(self):
        """Run recovery and normal message consumption continuously."""

        await self.initialize()

        logger.info("Email worker started")

        while True:
            try:
                await self.recover_pending_messages()
                await self.consume_once()

            except asyncio.CancelledError:
                raise

            except Exception:
                logger.exception(
                    "Worker consumption cycle failed"
                )

                await asyncio.sleep(2)

