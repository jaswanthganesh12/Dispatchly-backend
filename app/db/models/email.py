import uuid
from sqlalchemy import CheckConstraint

from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Email(Base):
    __tablename__ = "emails"


    __table_args__ = (
            CheckConstraint(
                "status IN ('QUEUED', 'PROCESSING', 'SUBMITTED', "
                "'RETRY', 'FAILED', 'DELIVERED', 'BOUNCED', "
                "'COMPLAINED', 'CANCELLED')",
                name="valid_status",
            ),
            CheckConstraint(
                "priority BETWEEN 1 AND 10",
                name="valid_priority",
            ),
            CheckConstraint(
                "attempts >= 0",
                name="non_negative_attempts",
            ),
            CheckConstraint(
                "max_attempts > 0",
                name="positive_max_attempts",
            ),
        )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    recipient_email: Mapped[str] = mapped_column(
        String(320),
        nullable=False,
    )

    sender_email: Mapped[str] = mapped_column(
        String(320),
        nullable=False,
    )

    subject: Mapped[str] = mapped_column(
        String(998),
        nullable=False,
    )

    html_body: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    text_body: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        default="QUEUED",
        nullable=False,
    )

    priority: Mapped[int] = mapped_column(
        SmallInteger,
        default=5,
        nullable=False,
    )

    attempts: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    max_attempts: Mapped[int] = mapped_column(
        Integer,
        default=5,
        nullable=False,
    )

    scheduled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


