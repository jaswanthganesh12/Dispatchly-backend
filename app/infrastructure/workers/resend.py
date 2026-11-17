
import httpx

from app.core.config import get_settings
from app.infrastructure.workers.provider import ProviderResult


class ResendEmailProvider:
    provider_name = "resend"
    API_URL = "https://api.resend.com/emails"

    def __init__(self):
        settings = get_settings()

        if not settings.RESEND_API_KEY:
            raise ValueError("RESEND_API_KEY is not configured")

        self.from_email = settings.RESEND_FROM_EMAIL

        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(
                connect=5.0,
                read=20.0,
                write=10.0,
                pool=5.0,
            ),
            headers={
                "Authorization": f"Bearer {settings.RESEND_API_KEY}",
                "Content-Type": "application/json",
            },
        )

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

        payload = {
            "from":self.from_email,
            "to": [recipient],
            "subject": subject,
        }

        if html_body:
            payload["html"] = html_body

        if text_body:
            payload["text"] = text_body

        try:
            response = await self.client.post(
                self.API_URL,
                json=payload,
                headers={
                    "Idempotency-Key": idempotency_key,
                },
            )

            if response.is_success:
                data = response.json()

                return ProviderResult(
                    success=True,
                    provider_name=self.provider_name,
                    provider_message_id=data.get("id"),
                )

            try:
                error_data = response.json()
                error_message = (
                    error_data.get("message")
                    or error_data.get("error")
                    or response.text
                )
                error_code = error_data.get("name", "RESEND_ERROR")
            except ValueError:
                error_message = response.text
                error_code = "RESEND_ERROR"

            retryable = (
                response.status_code == 408
                or response.status_code == 409
                or response.status_code == 429
                or response.status_code >= 500
            )

            return ProviderResult(
                success=False,
                provider_name=self.provider_name,
                error_code=str(error_code),
                error_message=str(error_message)[:2000],
                retryable=retryable,
            )

        except httpx.TimeoutException as exc:
            return ProviderResult(
                success=False,
                provider_name=self.provider_name,
                error_code="RESEND_TIMEOUT",
                error_message=str(exc)[:2000],
                retryable=True,
            )

        except httpx.NetworkError as exc:
            return ProviderResult(
                success=False,
                provider_name=self.provider_name,
                error_code="RESEND_NETWORK_ERROR",
                error_message=str(exc)[:2000],
                retryable=True,
            )

        except httpx.HTTPError as exc:
            return ProviderResult(
                success=False,
                provider_name=self.provider_name,
                error_code="RESEND_HTTP_ERROR",
                error_message=str(exc)[:2000],
                retryable=True,
            )

    async def close(self):
        await self.client.aclose()
