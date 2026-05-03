"""
Security utilities: JWT tokens, password hashing, rate limiting.
"""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import redis.asyncio as aioredis
from jose import JWTError, jwt
from passlib.context import CryptContext

from backend.config import settings
from backend.utils.logger import get_logger

logger = get_logger(__name__)

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ── Password utilities ─────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    """Hash a plain-text password using bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain-text password against a bcrypt hash."""
    return pwd_context.verify(plain_password, hashed_password)


# ── JWT utilities ──────────────────────────────────────────────────────────────

def create_access_token(
    subject: str | Any,
    expires_delta: Optional[timedelta] = None,
    extra_claims: Optional[dict] = None,
) -> str:
    """Create a signed JWT access token."""
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )

    payload = {
        "sub": str(subject),
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "access",
        "jti": secrets.token_hex(16),
    }
    if extra_claims:
        payload.update(extra_claims)

    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(subject: str | Any) -> str:
    """Create a signed JWT refresh token with longer expiry."""
    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.REFRESH_TOKEN_EXPIRE_DAYS
    )
    payload = {
        "sub": str(subject),
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "refresh",
        "jti": secrets.token_hex(16),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> dict:
    """Decode and verify a JWT token. Raises JWTError on failure."""
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])


def verify_token_type(payload: dict, expected_type: str) -> bool:
    """Ensure token is of the expected type (access or refresh)."""
    return payload.get("type") == expected_type


# ── Token Blacklist (Redis) ────────────────────────────────────────────────────

class TokenBlacklist:
    """Redis-backed JWT token blacklist for logout."""

    def __init__(self, redis_client: aioredis.Redis):
        self.redis = redis_client
        self.prefix = "blacklist:"

    async def blacklist_token(self, jti: str, expires_in: int) -> None:
        """Add a token JTI to the blacklist with TTL matching token expiry."""
        await self.redis.setex(f"{self.prefix}{jti}", expires_in, "1")
        logger.info("token_blacklisted", jti=jti)

    async def is_blacklisted(self, jti: str) -> bool:
        """Check if a token JTI is in the blacklist."""
        return bool(await self.redis.exists(f"{self.prefix}{jti}"))


# ── Input sanitization ────────────────────────────────────────────────────────

DANGEROUS_PATTERNS = [
    "selfdestruct",
    "suicide",
    "delegatecall",
    "__proto__",
    "eval(",
    "exec(",
    "import os",
    "import sys",
    "subprocess",
]


def sanitize_prompt(prompt: str) -> tuple[str, list[str]]:
    """
    Sanitize user AI prompt.
    Returns (cleaned_prompt, list_of_warnings).
    """
    warnings = []
    cleaned = prompt.strip()

    # Length check
    if len(cleaned) > 2000:
        cleaned = cleaned[:2000]
        warnings.append("Prompt truncated to 2000 characters")

    # Check for injection attempts
    lower = cleaned.lower()
    for pattern in DANGEROUS_PATTERNS:
        if pattern in lower:
            warnings.append(f"Potentially dangerous pattern detected: '{pattern}'")

    return cleaned, warnings


def sanitize_solidity_output(code: str) -> str:
    """
    Extract only the Solidity code block from AI output.
    Strips markdown fences, explanations, etc.
    """
    # Extract code between ```solidity ... ``` or ``` ... ```
    import re

    # Try to find solidity code block
    pattern = r"```(?:solidity)?\s*\n(.*?)```"
    matches = re.findall(pattern, code, re.DOTALL)
    if matches:
        # Return the longest match (most likely the full contract)
        return max(matches, key=len).strip()

    # If no code blocks found, return as-is after basic cleanup
    lines = code.split("\n")
    solidity_lines = []
    in_contract = False

    for line in lines:
        if line.strip().startswith("// SPDX") or line.strip().startswith("pragma"):
            in_contract = True
        if in_contract:
            solidity_lines.append(line)

    if solidity_lines:
        return "\n".join(solidity_lines).strip()

    return code.strip()


# ── API Key generation ─────────────────────────────────────────────────────────

def generate_api_key() -> str:
    """Generate a secure random API key."""
    return f"scg_{secrets.token_urlsafe(32)}"


def hash_api_key(api_key: str) -> str:
    """Hash an API key for secure storage."""
    return hashlib.sha256(api_key.encode()).hexdigest()
