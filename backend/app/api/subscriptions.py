"""Authenticated email-scoped subscription CRUD."""

from typing import Annotated

from fastapi import APIRouter, Path
from pydantic import EmailStr

from app.api.deps import DB, CurrentUser
from app.schemas.intelligence import EmailSubscriptionInput, EmailSubscriptionOut
from app.services import subscription_service

router = APIRouter(prefix="/api/subscriptions", tags=["subscriptions"])


@router.post("", response_model=EmailSubscriptionOut)
async def subscribe(
    payload: EmailSubscriptionInput, db: DB, user: CurrentUser
) -> EmailSubscriptionOut:
    """Subscribe the current account; another address requires administration."""
    return await subscription_service.save_subscription(
        db, user, payload, str(payload.email) if payload.email else None
    )


@router.get("/{email}", response_model=EmailSubscriptionOut)
async def subscription(
    email: Annotated[EmailStr, Path()], db: DB, user: CurrentUser
) -> EmailSubscriptionOut:
    return await subscription_service.get_subscription(db, user, str(email))


@router.delete("/{email}", status_code=204)
async def unsubscribe(
    email: Annotated[EmailStr, Path()], db: DB, user: CurrentUser
) -> None:
    await subscription_service.delete_subscription(db, user, str(email))
