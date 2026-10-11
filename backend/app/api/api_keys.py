"""Personal API key provisioning and required authentication for open API routes."""

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import APIKeyHeader
from sqlalchemy import select

from app.api.deps import DB, CurrentUser
from app.core.config import get_settings
from app.models import APIKey, User
from app.schemas.intelligence import APIKeyCreated, APIKeyInput, APIKeyOut

router = APIRouter(prefix="/api/api-keys", tags=["API keys"])
key_header = APIKeyHeader(
    name="X-API-Key", auto_error=False, scheme_name="MiningIntelAPIKey"
)


def key_digest(value: str) -> str:
    """Store an HMAC digest so leaked rows cannot be used as credentials."""
    return hmac.new(
        get_settings().SECRET_KEY.get_secret_value().encode(),
        value.encode(),
        hashlib.sha256,
    ).hexdigest()


async def optional_api_key(
    db: DB, key: Annotated[str | None, Depends(key_header)]
) -> User | None:
    """Validate supplied keys; allow anonymous website reads."""
    if key is None:
        return None
    if not 20 <= len(key) <= 200:
        raise HTTPException(401, "API Key 无效")
    row = (
        await db.execute(
            select(APIKey, User)
            .join(User)
            .where(
                APIKey.token_hash == key_digest(key),
                APIKey.revoked_at.is_(None),
                APIKey.expires_at > datetime.now(UTC),
                User.active.is_(True),
            )
        )
    ).first()
    if not row:
        raise HTTPException(401, "API Key 无效或已过期")
    return row[1]


async def required_api_key(
    user: Annotated[User | None, Depends(optional_api_key)],
) -> User:
    """Every /api/open endpoint requires a valid, active and unexpired key."""
    if user is None:
        raise HTTPException(401, "开放 API 需要 X-API-Key")
    return user


@router.post("", response_model=APIKeyCreated, status_code=201)
async def create_api_key(
    payload: APIKeyInput, db: DB, user: CurrentUser
) -> APIKeyCreated:
    """Return the secret once; cap active credentials per account."""
    await db.execute(select(User.id).where(User.id == user.id).with_for_update())
    count = (
        await db.scalars(
            select(APIKey.id).where(
                APIKey.user_id == user.id,
                APIKey.revoked_at.is_(None),
                APIKey.expires_at > datetime.now(UTC),
            )
        )
    ).all()
    if len(count) >= 10:
        raise HTTPException(409, "最多保留10个有效 API Key，请先撤销旧密钥")
    value = "mi_" + secrets.token_urlsafe(32)
    item = APIKey(
        user_id=user.id,
        name=payload.name.strip(),
        prefix=value[:12],
        token_hash=key_digest(value),
        expires_at=datetime.now(UTC) + timedelta(days=payload.expires_in_days),
    )
    db.add(item)
    await db.flush()
    return APIKeyCreated(**APIKeyOut.model_validate(item).model_dump(), key=value)


@router.get("", response_model=list[APIKeyOut])
async def list_api_keys(db: DB, user: CurrentUser) -> list[APIKey]:
    return list(
        (
            await db.scalars(
                select(APIKey)
                .where(APIKey.user_id == user.id)
                .order_by(APIKey.created_at.desc())
            )
        ).all()
    )


@router.delete("/{key_id}", status_code=204)
async def revoke_api_key(key_id: UUID, db: DB, user: CurrentUser) -> None:
    """Revoke only the current user's credential, without leaking other IDs."""
    item = await db.scalar(
        select(APIKey)
        .where(APIKey.id == key_id, APIKey.user_id == user.id)
        .with_for_update()
    )
    if item is None:
        raise HTTPException(404, "API Key 不存在")
    item.revoked_at = datetime.now(UTC)
