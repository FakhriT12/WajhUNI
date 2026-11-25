import hashlib
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from redis.asyncio import Redis
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.core.redis import get_redis
from app.core.security import (
    create_access_token,
    generate_opaque_token,
    hash_password,
    verify_password,
)
from app.models.models import EmailDomain, EmailVerificationToken, User
from app.schemas.auth import (
    LoginRequest,
    MessageResponse,
    RefreshRequest,
    RegisterRequest,
    RegisterResponse,
    TokenResponse,
    UserPublic,
    VerifyEmailRequest,
)

router = APIRouter(prefix="/auth", tags=["auth"])

_DUMMY_HASH = hash_password("not-a-real-password")


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    payload: RegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> RegisterResponse:
    email = str(payload.email).lower()
    domain = email.split("@", 1)[1]

    result = await db.execute(
        select(EmailDomain).where(
            EmailDomain.domain == domain,
            EmailDomain.is_active.is_(True),
        )
    )
    email_domain = result.scalar_one_or_none()
    if email_domain is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Your university is not yet on WajhUni.",
        )

    existing = await db.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none():
        return RegisterResponse(
            message="If this email is eligible, a verification link has been sent."
        )
    user = User(
        full_name=payload.full_name,
        email=email,
        password_hash=hash_password(payload.password),
        university_id=email_domain.university_id,
    )
    db.add(user)
    await db.flush()

    raw_token, token_hash = generate_opaque_token()
    db.add(
        EmailVerificationToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        )
    )

    # TODO(phase-1): replace with email sending via BackgroundTasks; remove this print
    if settings.ENVIRONMENT == "development":
        print(f"[DEV] verification token for {email}: {raw_token}")

    return RegisterResponse(
        message="If this email is eligible, a verification link has been sent."
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> TokenResponse:
    email = str(payload.email).lower()
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    password_ok = verify_password(
        payload.password,
        user.password_hash if user else _DUMMY_HASH,
    )
    if user is None or not password_ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    if user.verification_status == "pending":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Please verify your email before logging in.",
        )
    if user.verification_status != "verified":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account is not available.",
        )

    user.last_login = datetime.now(timezone.utc)

    access_token = create_access_token(str(user.id), user.role)
    raw_refresh, refresh_hash = generate_opaque_token()
    await redis.set(
        f"refresh:{refresh_hash}",
        str(user.id),
        ex=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600,
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=raw_refresh,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    payload: RefreshRequest,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> TokenResponse:
    old_hash = hashlib.sha256(payload.refresh_token.encode()).hexdigest()
    user_id = await redis.getdel(f"refresh:{old_hash}")

    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired refresh token.",
    )
    if user_id is None:
        raise unauthorized

    try:
        parsed_user_id = UUID(user_id)
    except ValueError:
        raise unauthorized from None

    result = await db.execute(select(User).where(User.id == parsed_user_id))
    user = result.scalar_one_or_none()
    if user is None or user.verification_status != "verified":
        raise unauthorized

    access_token = create_access_token(str(user.id), user.role)
    raw_refresh, new_hash = generate_opaque_token()
    await redis.set(
        f"refresh:{new_hash}",
        str(user.id),
        ex=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600,
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=raw_refresh,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    payload: RefreshRequest,
    redis: Redis = Depends(get_redis),
) -> None:
    token_hash = hashlib.sha256(payload.refresh_token.encode()).hexdigest()
    await redis.delete(f"refresh:{token_hash}")


@router.get("/me", response_model=UserPublic)
async def get_me(
    current_user: User = Depends(get_current_user),
) -> UserPublic:
    return UserPublic.model_validate(current_user)


@router.post("/verify-email", response_model=MessageResponse)
async def verify_email(
    payload: VerifyEmailRequest,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    token_hash = hashlib.sha256(payload.token.encode()).hexdigest()
    now = datetime.now(timezone.utc)

    result = await db.execute(
        update(EmailVerificationToken)
        .where(
            EmailVerificationToken.token_hash == token_hash,
            EmailVerificationToken.used_at.is_(None),
            EmailVerificationToken.expires_at > now,
        )
        .values(used_at=now)
        .returning(EmailVerificationToken.user_id)
    )
    user_id = result.scalar_one_or_none()

    invalid = HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="This verification link is invalid or has expired.",
    )
    if user_id is None:
        raise invalid

    result = await db.execute(
        update(User)
        .where(User.id == user_id, User.verification_status == "pending")
        .values(verification_status="verified")
    )
    if result.rowcount == 0:
        raise invalid

    return MessageResponse(message="Email verified. You can now log in.")
