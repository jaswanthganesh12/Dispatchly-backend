
from uuid import UUID

from sqlalchemy import func, select, update

from app.db.models import Email
from app.db.session import AsyncSessionLocal


async def process_email_record(email_id: str) -> dict:
    parsed_email_id = UUID(email_id)

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            update(Email)
            .where(
                Email.id == parsed_email_id,
                Email.status == "QUEUED",
            )
            .values(
                status="PROCESSING",
                updated_at=func.now(),
            )
            .returning(Email.id)
        )

        claimed_id = result.scalar_one_or_none()

        if claimed_id is None:
            result = await session.execute(
                select(Email.status).where(
                    Email.id == parsed_email_id
                )
            )

            current_status = result.scalar_one_or_none()

            if current_status is None:
                return {
                    "email_id": email_id,
                    "status": "NOT_FOUND",
                }

            return {
                "email_id": email_id,
                "status": "SKIPPED",
                "reason": f"Email is currently {current_status}",
            }

        await session.commit()

        return {
            "email_id": email_id,
            "status": "PROCESSING",
        }