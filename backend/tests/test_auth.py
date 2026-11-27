import base64
import json
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from app.core.security import create_access_token, generate_opaque_token
from app.models.models import EmailVerificationToken, University, User

AUTH_URL = "/api/v1/auth"
PASSWORD = "correct-horse-battery-staple"
UserFactory = Callable[..., Awaitable[User]]
LoginTokens = Callable[[User, str], Awaitable[dict[str, Any]]]


def _email(domain: str = "tbs.u-tunis.tn") -> str:
    return f"auth-{uuid4().hex}@{domain}"


async def _find_user(engine: AsyncEngine, email: str) -> User | None:
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        result = await session.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()


async def _count_users(engine: AsyncEngine, email: str) -> int:
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        result = await session.execute(
            select(func.count()).select_from(User).where(User.email == email)
        )
        return result.scalar_one()


async def _insert_verification_token(
    engine: AsyncEngine,
    user: User,
    *,
    expires_at: datetime,
) -> str:
    raw_token, token_hash = generate_opaque_token()
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        session.add(
            EmailVerificationToken(
                user_id=user.id,
                token_hash=token_hash,
                expires_at=expires_at,
            )
        )
        await session.commit()
    return raw_token


def _tamper_role_without_resigning(token: str) -> str:
    header, payload, signature = token.split(".")
    padded_payload = payload + "=" * (-len(payload) % 4)
    claims = json.loads(base64.urlsafe_b64decode(padded_payload))
    claims["role"] = "admin" if claims["role"] != "admin" else "student"
    changed_payload = base64.urlsafe_b64encode(
        json.dumps(claims, separators=(",", ":")).encode("utf-8")
    ).decode("ascii").rstrip("=")
    return f"{header}.{changed_payload}.{signature}"


@pytest.mark.asyncio
async def test_register_valid_tbs_domain_persists_pending_user(
    client: AsyncClient,
    engine: AsyncEngine,
    seeded_university: University,
) -> None:
    # Arrange
    email = _email()
    payload = {
        "full_name": "TBS Student",
        "email": email,
        "password": PASSWORD,
    }

    # Act
    response = await client.post(f"{AUTH_URL}/register", json=payload)

    # Assert
    assert response.status_code == 201
    user = await _find_user(engine, email)
    assert user is not None
    assert user.verification_status == "pending"
    assert user.password_hash.startswith(("$2a$", "$2b$", "$2y$"))
    assert user.password_hash != PASSWORD


@pytest.mark.asyncio
async def test_register_gmail_domain_is_rejected_without_creating_user(
    client: AsyncClient,
    engine: AsyncEngine,
    seeded_university: University,
) -> None:
    # Arrange
    email = _email("gmail.com")
    payload = {
        "full_name": "Unapproved Student",
        "email": email,
        "password": PASSWORD,
    }

    # Act
    response = await client.post(f"{AUTH_URL}/register", json=payload)

    # Assert
    assert response.status_code == 400
    assert await _count_users(engine, email) == 0


@pytest.mark.asyncio
async def test_register_same_email_twice_creates_one_user(
    client: AsyncClient,
    engine: AsyncEngine,
    seeded_university: University,
) -> None:
    # Arrange
    email = _email()
    payload = {
        "full_name": "Duplicate Student",
        "email": email,
        "password": PASSWORD,
    }

    # Act
    first_response = await client.post(f"{AUTH_URL}/register", json=payload)
    second_response = await client.post(f"{AUTH_URL}/register", json=payload)

    # Assert
    assert first_response.status_code == 201
    assert second_response.status_code == 201
    assert await _count_users(engine, email) == 1


@pytest.mark.asyncio
async def test_verify_email_with_valid_token_activates_user(
    client: AsyncClient,
    engine: AsyncEngine,
    make_user: UserFactory,
) -> None:
    # Arrange
    user = await make_user(verification_status="pending")
    raw_token = await _insert_verification_token(
        engine,
        user,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )

    # Act
    response = await client.post(
        f"{AUTH_URL}/verify-email", json={"token": raw_token}
    )

    # Assert
    assert response.status_code == 200
    stored_user = await _find_user(engine, user.email)
    assert stored_user is not None
    assert stored_user.verification_status == "verified"


@pytest.mark.asyncio
async def test_verify_email_reused_token_is_rejected(
    client: AsyncClient,
    engine: AsyncEngine,
    make_user: UserFactory,
) -> None:
    # Arrange
    user = await make_user(verification_status="pending")
    raw_token = await _insert_verification_token(
        engine,
        user,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )

    # Act
    first_response = await client.post(
        f"{AUTH_URL}/verify-email", json={"token": raw_token}
    )
    second_response = await client.post(
        f"{AUTH_URL}/verify-email", json={"token": raw_token}
    )

    # Assert
    assert first_response.status_code == 200
    assert second_response.status_code == 400


@pytest.mark.asyncio
async def test_verify_email_expired_token_keeps_user_pending(
    client: AsyncClient,
    engine: AsyncEngine,
    make_user: UserFactory,
) -> None:
    # Arrange
    user = await make_user(verification_status="pending")
    raw_token = await _insert_verification_token(
        engine,
        user,
        expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
    )

    # Act
    response = await client.post(
        f"{AUTH_URL}/verify-email", json={"token": raw_token}
    )

    # Assert
    assert response.status_code == 400
    stored_user = await _find_user(engine, user.email)
    assert stored_user is not None
    assert stored_user.verification_status == "pending"


@pytest.mark.asyncio
async def test_verify_email_rejects_garbage_and_short_tokens(
    client: AsyncClient,
    seeded_university: University,
) -> None:
    # Arrange
    garbage_token = f"garbage-{uuid4().hex}"

    # Act
    garbage_response = await client.post(
        f"{AUTH_URL}/verify-email", json={"token": garbage_token}
    )
    short_response = await client.post(
        f"{AUTH_URL}/verify-email", json={"token": "short"}
    )

    # Assert
    assert garbage_response.status_code == 400
    assert short_response.status_code == 422


@pytest.mark.asyncio
async def test_login_returns_access_and_refresh_tokens(
    login_tokens: LoginTokens,
    make_user: UserFactory,
) -> None:
    # Arrange
    user = await make_user()

    # Act
    tokens = await login_tokens(user, PASSWORD)

    # Assert
    assert tokens["access_token"]
    assert tokens["refresh_token"]
    assert tokens["expires_in"] == 900


@pytest.mark.asyncio
async def test_login_wrong_password_and_unknown_email_have_same_401_body(
    client: AsyncClient,
    make_user: UserFactory,
) -> None:
    # Arrange
    user = await make_user()

    # Act
    wrong_password_response = await client.post(
        f"{AUTH_URL}/login",
        json={"email": user.email, "password": "not-the-right-password"},
    )
    unknown_email_response = await client.post(
        f"{AUTH_URL}/login",
        json={"email": _email(), "password": PASSWORD},
    )

    # Assert
    assert wrong_password_response.status_code == 401
    assert unknown_email_response.status_code == 401
    assert wrong_password_response.json() == unknown_email_response.json()


@pytest.mark.asyncio
async def test_login_pending_user_is_forbidden(
    client: AsyncClient,
    make_user: UserFactory,
) -> None:
    # Arrange
    user = await make_user(verification_status="pending")

    # Act
    response = await client.post(
        f"{AUTH_URL}/login",
        json={"email": user.email, "password": PASSWORD},
    )

    # Assert
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_refresh_rotates_tokens_and_rejects_old_refresh_token(
    client: AsyncClient,
    login_tokens: LoginTokens,
    make_user: UserFactory,
) -> None:
    # Arrange
    user = await make_user()
    old_tokens = await login_tokens(user, PASSWORD)

    # Act
    response = await client.post(
        f"{AUTH_URL}/refresh",
        json={"refresh_token": old_tokens["refresh_token"]},
    )
    reused_response = await client.post(
        f"{AUTH_URL}/refresh",
        json={"refresh_token": old_tokens["refresh_token"]},
    )

    # Assert
    assert response.status_code == 200
    new_tokens = response.json()
    assert new_tokens["access_token"] != old_tokens["access_token"]
    assert new_tokens["refresh_token"] != old_tokens["refresh_token"]
    assert reused_response.status_code == 401


@pytest.mark.asyncio
async def test_logout_revokes_refresh_token_and_unknown_logout_succeeds(
    client: AsyncClient,
    login_tokens: LoginTokens,
    make_user: UserFactory,
) -> None:
    # Arrange
    user = await make_user()
    tokens = await login_tokens(user, PASSWORD)
    unknown_token = f"unknown-{uuid4().hex}"

    # Act
    logout_response = await client.post(
        f"{AUTH_URL}/logout",
        json={"refresh_token": tokens["refresh_token"]},
    )
    refresh_response = await client.post(
        f"{AUTH_URL}/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    unknown_logout_response = await client.post(
        f"{AUTH_URL}/logout",
        json={"refresh_token": unknown_token},
    )

    # Assert
    assert logout_response.status_code == 204
    assert refresh_response.status_code == 401
    assert unknown_logout_response.status_code == 204


@pytest.mark.asyncio
async def test_me_requires_valid_access_token_and_omits_password_hash(
    client: AsyncClient,
    make_user: UserFactory,
) -> None:
    # Arrange
    user = await make_user()
    access_token = create_access_token(str(user.id), user.role)

    # Act
    missing_response = await client.get(f"{AUTH_URL}/me")
    garbage_response = await client.get(
        f"{AUTH_URL}/me",
        headers={"Authorization": "Bearer not-a-valid-token"},
    )
    valid_response = await client.get(
        f"{AUTH_URL}/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    # Assert
    assert missing_response.status_code == 401
    assert garbage_response.status_code == 401
    assert valid_response.status_code == 200
    assert "password_hash" not in valid_response.json()
    assert valid_response.json()["email"] == user.email


@pytest.mark.asyncio
async def test_me_rejects_refresh_token_as_bearer(
    client: AsyncClient,
    login_tokens: LoginTokens,
    make_user: UserFactory,
) -> None:
    # Arrange
    user = await make_user()
    tokens = await login_tokens(user, PASSWORD)

    # Act
    response = await client.get(
        f"{AUTH_URL}/me",
        headers={"Authorization": f"Bearer {tokens['refresh_token']}"},
    )

    # Assert
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_me_rejects_user_suspended_after_access_token_issued(
    client: AsyncClient,
    engine: AsyncEngine,
    make_user: UserFactory,
) -> None:
    # Arrange
    user = await make_user()
    access_token = create_access_token(str(user.id), user.role)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        await session.execute(
            update(User)
            .where(User.id == user.id)
            .values(verification_status="suspended")
        )
        await session.commit()

    # Act
    response = await client.get(
        f"{AUTH_URL}/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    # Assert
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_me_rejects_access_token_with_tampered_role(
    client: AsyncClient,
    make_user: UserFactory,
) -> None:
    # Arrange
    user = await make_user()
    access_token = create_access_token(str(user.id), user.role)
    tampered_token = _tamper_role_without_resigning(access_token)

    # Act
    response = await client.get(
        f"{AUTH_URL}/me",
        headers={"Authorization": f"Bearer {tampered_token}"},
    )

    # Assert
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_student_cannot_access_admin_ping(
    client: AsyncClient,
    make_user: UserFactory,
) -> None:
    # Arrange
    student = await make_user(role="student")
    access_token = create_access_token(str(student.id), student.role)

    # Act
    response = await client.get(
        "/api/v1/admin/ping",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    # Assert
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_admin_can_access_admin_ping(
    client: AsyncClient,
    make_user: UserFactory,
) -> None:
    # Arrange
    admin = await make_user(role="admin")
    access_token = create_access_token(str(admin.id), admin.role)

    # Act
    response = await client.get(
        "/api/v1/admin/ping",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    # Assert
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
