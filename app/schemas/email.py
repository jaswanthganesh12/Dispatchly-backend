
from datetime import datetime
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    model_validator,
)


class EmailCreate(BaseModel):
    tenant_id: UUID

    recipient_email: EmailStr
    sender_email: EmailStr

    subject: str = Field(min_length=1, max_length=998)

    html_body: str | None = None
    text_body: str | None = None

    priority: int = Field(default=5, ge=1, le=10)
    scheduled_at: datetime | None = None

    @model_validator(mode="after")
    def validate_email_body(self):
        if not self.html_body and not self.text_body:
            raise ValueError(
                "At least one of html_body or text_body is required"
            )

        return self


class EmailResponse(BaseModel):
    id: UUID
    tenant_id: UUID

    recipient_email: EmailStr
    sender_email: EmailStr
    subject: str

    html_body: str | None
    text_body: str | None

    status: str
    priority: int
    attempts: int
    max_attempts: int

    scheduled_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
