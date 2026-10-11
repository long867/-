"""Database and ownership dependencies shared by routes."""

from typing import Annotated

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import decode_token
from app.models import User

DB = Annotated[AsyncSession, Depends(get_db)]
bearer = HTTPBearer(auto_error=False)


async def current_user(
    db: DB,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> User:
    """Resolve an active user; never trust an ID supplied by the client."""
    try:
        if credentials is None:
            raise ValueError("No credentials")
        user_id = decode_token(credentials.credentials)
    except (ValueError, jwt.PyJWTError) as exc:
        raise HTTPException(
            401, "登录已失效，请重新登录", headers={"WWW-Authenticate": "Bearer"}
        ) from exc
    user = await db.get(User, user_id)
    if user is None or not user.active:
        raise HTTPException(401, "用户不可用")
    return user


CurrentUser = Annotated[User, Depends(current_user)]


async def admin_user(user: CurrentUser) -> User:
    """Require an administrator for all operational mutations."""
    if not user.is_admin:
        raise HTTPException(403, "需要管理员权限")
    return user


AdminUser = Annotated[User, Depends(admin_user)]
