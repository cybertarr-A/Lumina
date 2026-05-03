"""
Authentication routes: register, login, logout, token refresh.
"""
import uuid
from datetime import timedelta

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.database import get_db
from backend.models.models import (
    LoginRequest,
    TokenResponse,
    User,
    UserCreate,
    UserResponse,
)
from backend.utils.logger import get_logger
from backend.utils.security import (
    TokenBlacklist,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
    verify_token_type,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])
logger = get_logger(__name__)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_redis() -> aioredis.Redis:
    client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        yield client
    finally:
        await client.aclose()


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
) -> User:
    """JWT-protected dependency — validates token and fetches user."""
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(token)
        if not verify_token_type(payload, "access"):
            raise credentials_exc
        user_id: str = payload.get("sub")
        jti: str = payload.get("jti", "")
        if not user_id:
            raise credentials_exc

        # Check blacklist
        blacklist = TokenBlacklist(redis)
        if await blacklist.is_blacklisted(jti):
            raise credentials_exc

    except JWTError:
        raise credentials_exc

    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise credentials_exc
    return user


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: UserCreate, db: AsyncSession = Depends(get_db)):
    """Create a new user account."""
    # Check email uniqueness
    result = await db.execute(select(User).where(User.email == payload.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already registered")

    # Check username uniqueness
    result = await db.execute(select(User).where(User.username == payload.username))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Username already taken")

    user = User(
        email=payload.email,
        username=payload.username,
        hashed_password=hash_password(payload.password),
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    logger.info("user_registered", user_id=str(user.id), email=user.email)
    return user


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Authenticate user and issue JWT tokens."""
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is inactive")

    access_token = create_access_token(str(user.id))
    refresh_token = create_refresh_token(str(user.id))
    logger.info("user_logged_in", user_id=str(user.id))

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    refresh_token_str: str,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    """Rotate access token using a valid refresh token."""
    credentials_exc = HTTPException(status_code=401, detail="Invalid refresh token")
    try:
        payload = decode_token(refresh_token_str)
        if not verify_token_type(payload, "refresh"):
            raise credentials_exc
        user_id = payload.get("sub")
        jti = payload.get("jti", "")
    except JWTError:
        raise credentials_exc

    blacklist = TokenBlacklist(redis)
    if await blacklist.is_blacklisted(jti):
        raise credentials_exc

    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise credentials_exc

    # Blacklist used refresh token
    await blacklist.blacklist_token(jti, settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400)

    new_access = create_access_token(str(user.id))
    new_refresh = create_refresh_token(str(user.id))

    return TokenResponse(
        access_token=new_access,
        refresh_token=new_refresh,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    token: str = Depends(oauth2_scheme),
    redis: aioredis.Redis = Depends(get_redis),
):
    """Blacklist the current access token."""
    try:
        payload = decode_token(token)
        jti = payload.get("jti", "")
        exp = payload.get("exp", 0)
        import time
        ttl = max(0, int(exp - time.time()))
        blacklist = TokenBlacklist(redis)
        await blacklist.blacklist_token(jti, ttl)
        logger.info("user_logged_out", jti=jti)
    except JWTError:
        pass  # Already expired token — no action needed


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """Get the current authenticated user's profile."""
    return current_user
