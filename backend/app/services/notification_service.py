"""Source-linked in-app notices, consent-aware SMTP and durable webhook dispatch."""

import asyncio
import base64
import hashlib
import hmac
import time
from datetime import UTC, datetime
from typing import Literal
from urllib.parse import urlsplit
from uuid import UUID

import httpx
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import SessionFactory
from app.models import Notice, NoticeDispatch, NoticeRead, Report, Subscription, User
from app.schemas.intelligence import NoticeOut, NoticePage
from app.services.digest_service import get_digest
from app.services.subscription_service import deliver_report, send_email
from pipeline.analyzers.price_analyzer import price_analysis
from pipeline.reporters.common import report_bounds

Channel = Literal["slack", "feishu", "wecom"]


def webhook_payload(channel: Channel, text: str) -> dict:
    """Build each platform's documented plain-text robot payload."""
    text = text[:1800]
    if channel == "slack":
        return {"text": text, "mrkdwn": False}
    if channel == "feishu":
        payload = {"msg_type": "text", "content": {"text": text}}
        secret = get_settings().FEISHU_WEBHOOK_SECRET.get_secret_value()
        if secret:
            timestamp = str(int(time.time()))
            key = f"{timestamp}\n{secret}".encode()
            payload.update(
                timestamp=timestamp,
                sign=base64.b64encode(
                    hmac.new(key, digestmod=hashlib.sha256).digest()
                ).decode(),
            )
        return payload
    return {"msgtype": "text", "text": {"content": text}}


async def send_webhook(channel: Channel, text: str) -> str:
    """Send a configured HTTPS robot message without logging its secret URL.

    No redirect follows and no automatic ambiguous retry can duplicate a message.
    A rate-limited delivery stays pending for the next dispatcher pass.
    """
    settings = get_settings()
    endpoint = getattr(settings, f"{channel.upper()}_WEBHOOK_URL").get_secret_value()
    if not settings.WEBHOOK_NOTIFICATIONS_ENABLED or not endpoint:
        return "disabled"
    parsed = urlsplit(endpoint)
    official = {
        "slack": {"hooks.slack.com", "hooks.slack-gov.com"},
        "feishu": {"open.feishu.cn", "open.larksuite.com"},
        "wecom": {"qyapi.weixin.qq.com"},
    }
    local_test = (
        settings.APP_ENV == "test"
        and parsed.hostname == "127.0.0.1"
        and parsed.scheme == "http"
    )
    if not local_test and (
        parsed.scheme != "https"
        or parsed.hostname not in official[channel]
        or parsed.username
        or parsed.password
    ):
        raise ValueError("Unsupported webhook endpoint")
    async with httpx.AsyncClient(timeout=10, follow_redirects=False) as client:
        response = await client.post(endpoint, json=webhook_payload(channel, text))
    if response.status_code == 429:
        return "rate_limited"
    if response.status_code != 200:
        raise RuntimeError(f"Webhook HTTP {response.status_code}")
    if channel == "slack":
        if response.text.strip() != "ok":
            raise RuntimeError("Slack rejected webhook")
    else:
        data = response.json()
        code = (
            data.get("code", data.get("StatusCode"))
            if channel == "feishu"
            else data.get("errcode")
        )
        if code != 0:
            raise RuntimeError("Robot rejected webhook")
    return "sent"


async def create_report_notice(db: AsyncSession, report: Report) -> UUID:
    """Create one notice per scheduled report, including explicit empty periods."""
    minerals = sorted(report.data_json.get("stats", {}).get("minerals", {}))
    regions = sorted(report.data_json.get("stats", {}).get("regions", {}))
    event_key = f"report:{report.id}"
    notice_id = await db.scalar(
        insert(Notice)
        .values(
            event_key=event_key,
            kind="report",
            title=report.title,
            body="新一期矿产资源报告已生成。",
            minerals=minerals,
            regions=regions,
            url=f"/digest?kind={report.kind}&report={report.id}",
            report_id=report.id,
        )
        .on_conflict_do_nothing(index_elements=[Notice.event_key])
        .returning(Notice.id)
    )
    return notice_id or await db.scalar(
        select(Notice.id).where(Notice.event_key == event_key)
    )


async def create_price_notices(db: AsyncSession) -> list[UUID]:
    """Publish one price warning per real comparable daily observation."""
    alerts, _ = await price_analysis(db)
    ids = []
    for alert in alerts:
        event_key = f"price:{alert.id}"
        notice_id = await db.scalar(
            insert(Notice)
            .values(
                event_key=event_key,
                kind="price_alert",
                title=f"{alert.mineral}价格异动 · {alert.change_pct:+}%",
                body=(
                    f"{alert.date} · {alert.product or alert.mineral} · "
                    f"{alert.price} {alert.currency}/{alert.unit}。"
                    f"相较 {alert.previous_date} 报价变化 {alert.change_pct:+}%。"
                ),
                minerals=[alert.mineral],
                regions=[],
                url=f"/minerals/{alert.mineral}",
                severity=alert.severity,
                price_id=alert.id,
            )
            .on_conflict_do_nothing(index_elements=[Notice.event_key])
            .returning(Notice.id)
        )
        ids.append(
            notice_id
            or await db.scalar(select(Notice.id).where(Notice.event_key == event_key))
        )
    return ids


async def public_notice(
    db: AsyncSession, notice: Notice, read: bool = False
) -> NoticeOut:
    """Revalidate report evidence so withdrawn prose is never exposed by a notice."""
    result = NoticeOut.model_validate(notice).model_copy(update={"read": read})
    if notice.report_id:
        report = await db.get(Report, notice.report_id)
        if report:
            current = await get_digest(
                db, report.kind, report_bounds(report.period_start, report.period_end)
            )
            result.body = (
                f"{current.stats.article_count} 篇文章 · "
                f"{current.stats.source_count} 个信源。"
                + (
                    current.content[:200]
                    if current.sources
                    else "该周期暂无已发布的真实资料。"
                )
            )
            result.minerals = sorted(current.stats.minerals)
            result.regions = sorted(current.stats.regions)
    return result


async def list_notices(
    db: AsyncSession, user: User, page: int, page_size: int
) -> NoticePage:
    """Return a stable account-private read state alongside public market notices."""
    read_ids = select(NoticeRead.notice_id).where(NoticeRead.user_id == user.id)
    total = await db.scalar(select(func.count()).select_from(Notice)) or 0
    unread = (
        await db.scalar(
            select(func.count()).select_from(Notice).where(Notice.id.not_in(read_ids))
        )
        or 0
    )
    rows = (
        await db.execute(
            select(Notice, Notice.id.in_(read_ids))
            .order_by(Notice.created_at.desc(), Notice.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()
    return NoticePage(
        items=[await public_notice(db, notice, read) for notice, read in rows],
        total=total,
        unread_count=unread,
        page=page,
        page_size=page_size,
    )


async def mark_read(
    db: AsyncSession, user: User, notice_id: UUID | None = None
) -> None:
    """Mark only the authenticated user's notices; bulk marking is bounded by SQL."""
    if notice_id:
        if not await db.get(Notice, notice_id):
            raise HTTPException(404, "通知不存在")
        await db.execute(
            insert(NoticeRead)
            .values(user_id=user.id, notice_id=notice_id)
            .on_conflict_do_nothing(constraint="uq_notice_read")
        )
    else:
        rows = (
            await db.scalars(
                select(Notice.id).where(
                    Notice.id.not_in(
                        select(NoticeRead.notice_id).where(
                            NoticeRead.user_id == user.id
                        )
                    )
                )
            )
        ).all()
        if rows:
            await db.execute(
                insert(NoticeRead)
                .values([{"user_id": user.id, "notice_id": item} for item in rows])
                .on_conflict_do_nothing(constraint="uq_notice_read")
            )


async def prepare_dispatches(db: AsyncSession, notice_id: UUID) -> None:
    """Prepare durable work for configured channels and opted-in subscribers."""
    settings = get_settings()
    notice = await db.get(Notice, notice_id)
    if not notice:
        return
    recipients = []
    if settings.WEBHOOK_NOTIFICATIONS_ENABLED:
        recipients += [
            f"webhook:{name}"
            for name in ("slack", "feishu", "wecom")
            if getattr(settings, f"{name.upper()}_WEBHOOK_URL").get_secret_value()
        ]
    if settings.EMAIL_NOTIFICATIONS_ENABLED:
        subscriptions = (
            await db.scalars(
                select(Subscription)
                .join(User)
                .where(
                    Subscription.email_enabled.is_(True),
                    User.active.is_(True),
                )
            )
        ).all()
        for item in subscriptions:
            if notice.kind == "price_alert" and not item.price_alerts_enabled:
                continue
            if notice.kind == "report":
                report = await db.get(Report, notice.report_id)
                if not report or item.frequency != report.kind:
                    continue
            if item.subscribed_minerals and not set(item.subscribed_minerals) & set(
                notice.minerals
            ):
                continue
            if item.subscribed_regions and not set(item.subscribed_regions) & set(
                notice.regions
            ):
                continue
            recipients.append(f"email:{item.id}")
    for recipient in recipients:
        await db.execute(
            insert(NoticeDispatch)
            .values(notice_id=notice_id, recipient=recipient)
            .on_conflict_do_nothing(constraint="uq_notice_dispatch")
        )


async def dispatch_one(dispatch_id: UUID) -> dict:
    """Claim once before network IO; record uncertain results for explicit review."""
    async with SessionFactory.begin() as db:
        work = await db.scalar(
            select(NoticeDispatch)
            .where(NoticeDispatch.id == dispatch_id)
            .with_for_update()
        )
        if not work or work.status != "pending":
            return {"status": "already_claimed"}
        notice = await db.get(Notice, work.notice_id)
        if not notice:
            return {"status": "skipped"}
        work.status, work.attempts = "sending", work.attempts + 1
        work.claimed_at = datetime.now(UTC)
        recipient, report_id = work.recipient, notice.report_id
        output = await public_notice(db, notice)
        subscription_id = (
            UUID(recipient.split(":", 1)[1]) if recipient.startswith("email:") else None
        )
        address = None
        if subscription_id:
            subscription = await db.get(Subscription, subscription_id)
            user = await db.get(User, subscription.user_id) if subscription else None
            if (
                subscription
                and subscription.email_enabled
                and user
                and user.active
                and (notice.kind == "report" or subscription.price_alerts_enabled)
                and (
                    not subscription.subscribed_minerals
                    or set(subscription.subscribed_minerals) & set(output.minerals)
                )
                and (
                    not subscription.subscribed_regions
                    or set(subscription.subscribed_regions) & set(output.regions)
                )
            ):
                address = user.email
    status, error_type = "skipped", None
    try:
        if recipient.startswith("webhook:"):
            channel = recipient.split(":", 1)[1]
            link = get_settings().PUBLIC_SITE_URL.rstrip("/") + output.url
            status = await send_webhook(
                channel, f"MiningIntel · {output.title}\n{output.body}\n{link}"
            )
        elif address and report_id:
            result = await deliver_report(subscription_id, report_id)
            status = result["status"]
        elif address:
            await asyncio.to_thread(
                send_email,
                address,
                output.title,
                output.body
                + "\n"
                + get_settings().PUBLIC_SITE_URL.rstrip("/")
                + output.url,
                str(dispatch_id),
            )
            status = "sent"
    except Exception as exc:
        status, error_type = "needs_review", type(exc).__name__
    async with SessionFactory.begin() as db:
        work = await db.get(NoticeDispatch, dispatch_id)
        if work:
            if status == "rate_limited":
                work.status = "pending" if work.attempts < 5 else "needs_review"
                work.last_error = "RateLimitExhausted" if work.attempts >= 5 else None
            else:
                work.status, work.last_error = status, error_type
            if status == "sent":
                work.sent_at = datetime.now(UTC)
    return {"status": status, "error_type": error_type}
