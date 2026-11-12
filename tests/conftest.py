
import pytest_asyncio

from httpx import ASGITransport, AsyncClient
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings
from app.db.base import Base
from app.db.dependencies import get_db_session
from app.db.models import Email, Tenant
from app.main import app


@pytest_asyncio.fixture
async def test_engine():
    database_url = get_settings().TEST_DATABASE_URL
    parsed_url = make_url(database_url)

    # Safety guard: never run destructive cleanup on another database.
    if parsed_url.database != "dispatchly_test":
        raise RuntimeError(
            "Tests can only run against dispatchly_test"
        )

    engine = create_async_engine(
        database_url,
        pool_pre_ping=True,
    )

    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        yield engine

    finally:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.drop_all)

        await engine.dispose()


@pytest_asyncio.fixture
async def client(test_engine):
    TestSessionLocal = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async def override_get_db_session():
        async with TestSessionLocal() as session:
            yield session

    app.dependency_overrides[get_db_session] = (
        override_get_db_session
    )

    transport = ASGITransport(app=app)

    try:
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as test_client:
            yield test_client

    finally:
        app.dependency_overrides.pop(get_db_session, None)
