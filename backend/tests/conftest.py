import asyncio
import os
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from redis import asyncio as aioredis
from redis.asyncio import Redis
from sqlalchemy import delete
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.core.database import Base, get_db
from app.core.redis import get_redis
from app.core.security import hash_password
from app.main import app
from app.models.models import EmailDomain, University, User

if os.name == "nt":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

PASSWORD = "correct-horse-battery-staple"
TEST_REDIS_URL = os.getenv("TEST_REDIS_URL", "redis://localhost:6379/1")


def _test_database_url() -> str:
    configured_url = os.getenv("TEST_DATABASE_URL")
    if configured_url:
        url = make_url(configured_url)
    else:
        url = make_url(settings.DATABASE_URL).set(database="wajhuni_test")

    if url.database != "wajhuni_test":
        raise ValueError(
            "Tests require TEST_DATABASE_URL to target the wajhuni_test database."
        )
    return url.render_as_string(hide_password=False)


def _validate_test_redis_url() -> None:
    url = make_url(TEST_REDIS_URL)
    if (
        url.drivername != "redis"
        or url.host not in ("localhost", "127.0.0.1")
        or url.port != 6379
        or url.database != "1"
    ):
        raise ValueError(
            "Tests must use Redis DB 1 at redis://localhost:6379/1."
        )


@pytest_asyncio.fixture
async def engine() -> AsyncIterator[AsyncEngine]:
    test_engine = create_async_engine(
        _test_database_url(),
        echo=False,
        poolclass=NullPool,
    )
    initialized = False
    try:
        async with test_engine.begin() as connection:
            await connection.run_sync(Base.metadata.drop_all)
            await connection.run_sync(Base.metadata.create_all)
        initialized = True
        yield test_engine
    finally:
        if initialized:
            async with test_engine.begin() as connection:
                await connection.run_sync(Base.metadata.drop_all)
        await test_engine.dispose()


@pytest_asyncio.fixture
async def redis_test() -> AsyncIterator[Redis]:
    _validate_test_redis_url()
    redis_client = aioredis.from_url(TEST_REDIS_URL, decode_responses=True)
    try:
        await redis_client.flushdb()
        yield redis_client
    finally:
        await redis_client.aclose()


@pytest_asyncio.fixture
async def client(
    engine: AsyncEngine,
    redis_test: Redis,
) -> AsyncIterator[AsyncClient]:
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_db() -> AsyncIterator[Any]:
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def override_get_redis() -> Redis:
        return redis_test

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = override_get_redis
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def seeded_university(engine: AsyncEngine) -> University:
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    university = University(
        name_ar="جامعة اختبار",
        name_fr="Universite de test",
        acronym=f"T{uuid4().hex[:8].upper()}",
        type="public",
    )
    async with session_factory() as session:
        session.add(university)
        await session.flush()
        session.add(
            EmailDomain(
                university_id=university.id,
                domain="tbs.u-tunis.tn",
                is_active=True,
            )
        )
        await session.commit()
    return university


@pytest.fixture
def make_user(
    engine: AsyncEngine,
    seeded_university: University,
) -> Callable[..., Awaitable[User]]:
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def create_user(
        email: str | None = None,
        password: str = PASSWORD,
        role: str = "student",
        verification_status: str = "verified",
    ) -> User:
        user = User(
            full_name="Auth Test User",
            email=email or f"auth-{uuid4().hex}@tbs.u-tunis.tn",
            password_hash=hash_password(password),
            role=role,
            verification_status=verification_status,
            university_id=seeded_university.id,
        )
        async with session_factory() as session:
            session.add(user)
            await session.commit()
            await session.refresh(user)
        return user

    return create_user


@pytest.fixture
def login_tokens(
    client: AsyncClient,
) -> Callable[[User, str], Awaitable[dict[str, Any]]]:
    async def login(user: User, password: str = PASSWORD) -> dict[str, Any]:
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": password},
        )
        response.raise_for_status()
        return response.json()

    return login
