
from dataclasses import dataclass
from typing import Protocol


@dataclass
class ProviderResult:
    success: bool
    provider_name: str
    provider_message_id: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    retryable: bool = False


class EmailProvider(Protocol):
    provider_name: str

    async def send(
        self,
        *,
        recipient: str,
        sender: str,
        subject: str,
        html_body: str | None,
        text_body: str | None,
        idempotency_key: str,
    ) -> ProviderResult:
        ...

    async def close(self) -> None:
        ...


class FakeEmailProvider:
    provider_name = "fake-provider"

    async def send(
        self,
        *,
        recipient: str,
        sender: str,
        subject: str,
        html_body: str | None,
        text_body: str | None,
        idempotency_key: str,
    ) -> ProviderResult:
        from uuid import uuid4

        return ProviderResult(
            success=True,
            provider_name=self.provider_name,
            provider_message_id=f"fake-{uuid4()}",
        )

    async def close(self) -> None:
        return None

