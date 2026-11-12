from typing import Annotated
from sqlalchemy.exc import IntegrityError

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.dependencies import get_db_session
from app.db.models import Tenant
from app.schemas.tenant import TenantCreate, TenantResponse
from fastapi import Query
from sqlalchemy import select
from uuid import UUID


router = APIRouter(
    prefix="/v1/tenants",
    tags=["Tenants"],
)


@router.post(
    "",
    response_model=TenantResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_tenant(
    tenant_data: TenantCreate,
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    

    tenant = Tenant(
        name=tenant_data.name,
        slug=tenant_data.slug,
    )

    db.add(tenant)

    try:
        await db.commit()
        await db.refresh(tenant)

    except IntegrityError:
        await db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A tenant with this slug already exists",
        )

    return tenant

@router.get(
    "",
    response_model=list[TenantResponse],
)
async def list_tenants(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    query = (
        select(Tenant)
        .order_by(Tenant.created_at.desc())
        .limit(limit)
        .offset(offset)
    )

    result = await db.execute(query)

    return result.scalars().all()

@router.get(
    "/{tenant_id}",
    response_model=TenantResponse,
)
async def get_tenant(
    tenant_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    query = select(Tenant).where(Tenant.id == tenant_id)

    result = await db.execute(query)

    tenant = result.scalar_one_or_none()

    if tenant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )

    return tenant


