from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from redis.asyncio import Redis
from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import engine


settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.redis = Redis.from_url(
        settings.REDIS_URL,
        decode_responses=True,
    )

    yield

    await app.state.redis.aclose()
    await engine.dispose()


app = FastAPI(
    title=settings.APP_NAME,
    version="0.1.0",
    description="Reliable email delivery infrastructure",
    lifespan=lifespan,
)


@app.get("/health", tags=["Health"])
async def health():
    return {
        "status": "alive",
        "service": settings.APP_NAME,
    }


@app.get("/ready", tags=["Health"])
async def readiness():
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))

        await app.state.redis.ping()

        return {
            "status": "ready",
            "database": "connected",
            "redis": "connected",
        }

    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="One or more dependencies are unavailable",
        ) from exc

