"""Real PostgreSQL archives, notification deduplication and private read states."""

from datetime import UTC, datetime
from uuid import UUID

import pytest
from sqlalchemy import delete
from test_business_api import business as business
from test_notification_transports import smtp_receiver as smtp_receiver
from test_notification_transports import webhook_receiver as webhook_receiver

from app.models import Article, Notice, NoticeDispatch, Report, Subscription, User
from app.services.notification_service import (
    create_report_notice,
    list_notices,
    mark_read,
)
from app.services.report_service import get_report
from pipeline.reporters.common import build_report

pytestmark = pytest.mark.integration


async def test_rate_limited_dispatch_stops_after_five_actual_attempts(
    business, webhook_receiver, monkeypatch
):
    from app.core.config import Settings
    from app.services import notification_service

    settings = Settings(
        APP_ENV="test",
        WEBHOOK_NOTIFICATIONS_ENABLED=True,
        WECOM_WEBHOOK_URL=(
            f"http://127.0.0.1:{webhook_receiver.server_address[1]}/limited"
        ),
    )
    monkeypatch.setattr(notification_service, "get_settings", lambda: settings)
    notice_id = None
    try:
        async with business["factory"].begin() as db:
            notice = Notice(
                event_key=f"rate-limit:{business['user_id']}",
                kind="price_alert",
                title="本地重试验证",
                body="本地接收端返回 429",
                url="/trends",
                minerals=[],
                regions=[],
            )
            db.add(notice)
            await db.flush()
            notice_id = notice.id
            dispatch = NoticeDispatch(
                notice_id=notice_id, recipient="webhook:wecom", attempts=4
            )
            db.add(dispatch)
            await db.flush()
            dispatch_id = dispatch.id
        assert (await notification_service.dispatch_one(dispatch_id))[
            "status"
        ] == "rate_limited"
        async with business["factory"]() as db:
            saved = await db.get(NoticeDispatch, dispatch_id)
            assert saved.status == "needs_review"
            assert saved.attempts == 5 and saved.claimed_at is not None
            assert saved.last_error == "RateLimitExhausted"
        assert (await notification_service.dispatch_one(dispatch_id))[
            "status"
        ] == "already_claimed"
        assert len(webhook_receiver.messages) == 1
    finally:
        if notice_id:
            async with business["factory"].begin() as db:
                await db.execute(delete(Notice).where(Notice.id == notice_id))


async def test_previous_report_is_idempotent_published_date_based_with_private_reads(
    business,
):
    factory = business["factory"]
    now = datetime(2024, 2, 12, 1, tzinfo=UTC)
    report_id = None
    try:
        async with factory.begin() as db:
            for article_id in business["ids"]:
                article = await db.get(Article, article_id)
                article.published_at = datetime(2024, 2, 7, 5, tzinfo=UTC)
                article.fetched_at = datetime(2026, 10, 11, tzinfo=UTC)
        result = await build_report("weekly", now)
        report_id = UUID(result["report_id"])
        assert result["articles"] == 3
        repeated = await build_report("weekly", now)
        assert repeated["status"] == "unchanged" and repeated["report_id"] == str(
            report_id
        )
        async with factory.begin() as db:
            report = await db.get(Report, report_id)
            assert report.period_start.isoformat() == "2024-02-05"
            assert report.period_end.isoformat() == "2024-02-12"
            assert len(report.data_json["analysis"]["coverage_by_day"]) == 7
            assert report.data_json["analysis"]["coverage_by_day"][2]["count"] == 3
            first = await create_report_notice(db, report)
            second = await create_report_notice(db, report)
            assert first == second
            owner, other = (
                await db.get(User, business["user_id"]),
                await db.get(User, business["other_id"]),
            )
            await mark_read(db, owner, first)
            assert (await list_notices(db, owner, 1, 50)).unread_count + 1 == (
                await list_notices(db, other, 1, 50)
            ).unread_count
            one = await get_report(db, report_id)
            assert one.stats.article_count == 3 and one.scheduled
        response = await business["client"].get(f"/api/digest/reports/{report_id}")
        assert response.status_code == 200 and len(response.json()["sources"]) == 3
        private = await business["client"].get("/api/notifications")
        assert private.status_code == 401
        owned = await business["client"].get(
            "/api/notifications", headers=business["headers"]
        )
        assert owned.status_code == 200 and owned.headers["cache-control"] == "no-store"
        async with factory.begin() as db:
            article = await db.get(Article, business["ids"][0])
            article.status = "pending"
        async with factory() as db:
            changed = await get_report(db, report_id)
            assert changed.stats.article_count == 2
            assert all(
                item.article_id != business["ids"][0] for item in changed.sources
            )
            assert (
                not changed.analysis
            )  # Stale structured event/policy evidence is discarded too.
    finally:
        if report_id:
            async with factory.begin() as db:
                await db.execute(delete(Report).where(Report.id == report_id))


async def test_empty_completed_period_is_stored_honestly(business):
    report_id = None
    try:
        result = await build_report("monthly", datetime(2023, 3, 1, 1, tzinfo=UTC))
        report_id = UUID(result["report_id"])
        assert result["articles"] == 0 and result["mode"] == "empty"
        async with business["factory"]() as db:
            report = await get_report(db, report_id)
            assert not report.sources and "暂无" in report.content
            assert len(report.analysis["coverage_by_day"]) == 28
    finally:
        if report_id:
            async with business["factory"].begin() as db:
                await db.execute(delete(Notice).where(Notice.report_id == report_id))
                await db.execute(delete(Report).where(Report.id == report_id))


async def test_opted_in_report_sends_once_through_real_smtp(
    business, smtp_receiver, monkeypatch
):
    from sqlalchemy import select

    from app.core.config import Settings
    from app.services import notification_service, subscription_service

    settings = Settings(
        APP_ENV="test",
        EMAIL_NOTIFICATIONS_ENABLED=True,
        WEBHOOK_NOTIFICATIONS_ENABLED=False,
        SMTP_HOST="127.0.0.1",
        SMTP_PORT=smtp_receiver.server_address[1],
        SMTP_FROM="miningintel@localhost",
        SMTP_STARTTLS=False,
        SMTP_SSL=False,
        SMTP_USERNAME="",
    )
    monkeypatch.setattr(notification_service, "get_settings", lambda: settings)
    monkeypatch.setattr(subscription_service, "get_settings", lambda: settings)
    factory = business["factory"]
    report_id = None
    try:
        async with factory.begin() as db:
            for article_id in business["ids"]:
                article = await db.get(Article, article_id)
                article.published_at = datetime(2024, 2, 7, 5, tzinfo=UTC)
            db.add(
                Subscription(
                    user_id=business["user_id"],
                    subscribed_minerals=["铜"],
                    subscribed_regions=[business["region"]],
                    frequency="weekly",
                    email_enabled=True,
                )
            )
        result = await build_report("weekly", datetime(2024, 2, 12, 1, tzinfo=UTC))
        report_id = UUID(result["report_id"])
        async with factory.begin() as db:
            report = await db.get(Report, report_id)
            notice_id = await create_report_notice(db, report)
            await notification_service.prepare_dispatches(db, notice_id)
            await notification_service.prepare_dispatches(db, notice_id)
            dispatches = (
                await db.scalars(
                    select(NoticeDispatch.id).where(
                        NoticeDispatch.notice_id == notice_id
                    )
                )
            ).all()
            assert len(dispatches) == 1
        assert (await notification_service.dispatch_one(dispatches[0]))[
            "status"
        ] == "sent"
        assert (await notification_service.dispatch_one(dispatches[0]))[
            "status"
        ] == "already_claimed"
        assert len(smtp_receiver.messages) == 1
    finally:
        if report_id:
            async with factory.begin() as db:
                await db.execute(delete(Report).where(Report.id == report_id))
