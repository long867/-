"""Password hashing and short-lived signed access tokens."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from pwdlib import PasswordHash

from app.core.config import get_settings

password_hasher = PasswordHash.recommended()


def hash_password(password: str) -> str:
    """Hash a password with Argon2id."""
    return password_hasher.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    """Verify a supplied password against its stored hash."""
    return password_hasher.verify(password, hashed)


def create_token(user_id: UUID) -> str:
    """Issue a token restricted to this API's issuer and audience."""
    settings = get_settings()
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "sub": str(user_id),
            "iat": now,
            "exp": now + timedelta(minutes=settings.ACCESS_TOKEN_MINUTES),
            "iss": "miningintel",
            "aud": "miningintel-api",
        },
        settings.SECRET_KEY.get_secret_value(),
        algorithm="HS256",
    )


def decode_token(token: str) -> UUID:
    """Validate signature, expiration, issuer and audience."""
    payload = jwt.decode(
        token,
        get_settings().SECRET_KEY.get_secret_value(),
        algorithms=["HS256"],
        issuer="miningintel",
        audience="miningintel-api",
        options={"require": ["sub", "iat", "exp", "iss", "aud"]},
    )
    return UUID(payload["sub"])
