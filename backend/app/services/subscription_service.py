"""Account-owned subscriptions and opt-in, source-linked SMTP notifications."""

import asyncio
import smtplib
import ssl
from datetime import UTC, datetime
from email.message import EmailMessage
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import SessionFactory
from app.models import NotificationDelivery, Report, Subscription, User
from app.schemas.api import SubscriptionInput
from app.schemas.intelligence import EmailSubscriptionOut


def authorize_email(user: User, email: str) -> str:
    """Prevent enumeration or mutation of another user's email preferences."""
    normalized = email.strip().lower()
    if normalized != user.email and not user.is_admin:
        raise HTTPException(403, "只能管理自己账户的订阅")
    return normalized


async def get_subscription(
    db: AsyncSession, user: User, email: str
) -> EmailSubscriptionOut:
    normalized = authorize_email(user, email)
    row = (
        await db.execute(
            select(Subscription, User.email).join(User).where(User.email == normalized)
        )
    ).first()
    if row is None:
        raise HTTPException(404, "尚未创建订阅")
    item, address = row
    return EmailSubscriptionOut(**item.__dict__, email=address)


async def save_subscription(
    db: AsyncSession, user: User, payload: SubscriptionInput, email: str | None = None
) -> EmailSubscriptionOut:
    """Upsert one account subscription; SMTP remains disabled unless configured."""
    normalized = authorize_email(user, email or user.email)
    owner = await db.scalar(
        select(User).where(User.email == normalized, User.active.is_(True))
    )
    if owner is None:
        raise HTTPException(404, "订阅账户不存在")
    values = payload.model_dump(exclude={"email"})
    await db.execute(
        insert(Subscription)
        .values(user_id=owner.id, **values)
        .on_conflict_do_update(index_elements=[Subscription.user_id], set_=values)
    )
    return await get_subscription(db, user, normalized)


async def delete_subscription(db: AsyncSession, user: User, email: str) -> None:
    normalized = authorize_email(user, email)
    item = await db.scalar(
        select(Subscription).join(User).where(User.email == normalized)
    )
    if item:
        await db.delete(item)


def send_email(email: str, title: str, body: str, message_id: str) -> None:
    """Send one opted-in digest with STARTTLS and an account-scoped Message-ID."""
    settings = get_settings()
    if (
        not settings.EMAIL_NOTIFICATIONS_ENABLED
        or not settings.SMTP_HOST
        or not settings.SMTP_FROM
    ):
        raise RuntimeError("SMTP notifications are not enabled and configured")
    message = EmailMessage()
    message["From"] = settings.SMTP_FROM
    message["To"] = email
    message["Subject"] = title
    message["Message-ID"] = f"<{message_id}@miningintel.local>"
    message.set_content(body)
    tls_context = ssl.create_default_context()
    smtp = smtplib.SMTP_SSL if settings.SMTP_SSL else smtplib.SMTP
    options = {"context": tls_context} if settings.SMTP_SSL else {}
    with smtp(settings.SMTP_HOST, settings.SMTP_PORT, timeout=20, **options) as client:
        if settings.SMTP_STARTTLS and not settings.SMTP_SSL:
            client.starttls(context=tls_context)
        if settings.SMTP_USERNAME:
            client.login(
                settings.SMTP_USERNAME, settings.SMTP_PASSWORD.get_secret_value()
            )
        client.send_message(message)


async def deliver_report(subscription_id: UUID, report_id: UUID) -> dict:
    """Claim a delivery once; leave uncertain SMTP results for manual review."""
    if not get_settings().EMAIL_NOTIFICATIONS_ENABLED:
        return {"status": "disabled"}
    async with SessionFactory.begin() as db:
        subscription = await db.get(Subscription, subscription_id)
        report = await db.get(Report, report_id)
        if (
            not subscription
            or not subscription.email_enabled
            or not report
            or subscription.frequency != report.kind
        ):
            return {"status": "skipped"}
        user = await db.get(User, subscription.user_id)
        if not user or not user.active:
            return {"status": "skipped"}
        article_ids = [UUID(item["article_id"]) for item in report.sources_json]
        from app.models import Article
        from app.services.article_service import public_conditions

        stmt = select(Article).where(Article.id.in_(article_ids), *public_conditions())
        if subscription.subscribed_minerals:
            stmt = stmt.where(
                Article.minerals.overlap(subscription.subscribed_minerals)
            )
        if subscription.subscribed_regions:
            stmt = stmt.where(Article.regions.overlap(subscription.subscribed_regions))
        matching = (await db.scalars(stmt)).all()
        if not matching:
            return {"status": "no_matching_articles"}
        delivery_id = await db.scalar(
            insert(NotificationDelivery)
            .values(subscription_id=subscription.id, report_id=report.id, attempts=1)
            .on_conflict_do_nothing(constraint="uq_notification_report")
            .returning(NotificationDelivery.id)
        )
        if delivery_id is None:
            return {"status": "already_claimed"}
        # Send only matching published evidence, avoiding unrelated or withdrawn prose.
        body = "\n\n".join(
            f"{article.title_zh or article.title}\n"
            f"{article.summary_zh or article.summary or ''}\n{article.url}"
            for article in matching
        )
        address, title = user.email, report.title
    try:
        await asyncio.to_thread(send_email, address, title, body, str(delivery_id))
    except (OSError, smtplib.SMTPException, RuntimeError) as exc:
        async with SessionFactory.begin() as db:
            delivery = await db.get(NotificationDelivery, delivery_id)
            if delivery:
                delivery.last_error = type(exc).__name__
        return {"status": "needs_review", "error_type": type(exc).__name__}
    async with SessionFactory.begin() as db:
        delivery = await db.get(NotificationDelivery, delivery_id)
        if delivery:
            delivery.sent_at = datetime.now(UTC)
    return {"status": "sent"}
