"""Verify real report archives, market windows and account-owned notice state."""

import asyncio
import json
import secrets
import sys
from pathlib import Path
from uuid import uuid4

import httpx
from app.core.db import SessionFactory
from app.core.security import hash_password
from app.models import NoticeRead, Subscription, User
from playwright.async_api import async_playwright, expect
from sqlalchemy import delete, func, select

ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:3000"


async def run() -> None:
    """Use actual API responses; create and clean up only a temporary QA account."""
    user_id = uuid4()
    email = f"phase5-ui-{user_id}@example.com"
    password = secrets.token_urlsafe(24)
    errors: list[str] = []
    checks: dict[str, object] = {}
    snapshots = ROOT / "docs/phase5-screenshots"
    snapshots.mkdir(exist_ok=True)
    async with httpx.AsyncClient(base_url=BASE, timeout=30) as api:
        payload = (await api.get("/api/digest/reports")).raise_for_status().json()
        reports = {item["kind"]: item for item in payload["items"]}
        assert {"daily", "weekly", "monthly"}.issubset(reports)
        assert all(
            "example.com" not in source["url"]
            for item in reports.values()
            for source in item["sources"]
        )
        checks["reports"] = {
            kind: {
                "id": row["id"],
                "articles": row["stats"]["article_count"],
                "mode": row["mode"],
            }
            for kind, row in reports.items()
        }
    try:
        async with SessionFactory.begin() as db:
            db.add(User(id=user_id, email=email, password_hash=hash_password(password)))
        async with async_playwright() as runtime:
            browser = await runtime.chromium.launch(
                channel="msedge" if sys.platform == "win32" else None, headless=True
            )
            page = await browser.new_page(viewport={"width": 1440, "height": 1080})
            page.on("pageerror", lambda error: errors.append(str(error)))
            await page.goto(BASE + "/trends")
            await expect(page.locator(".directory-card").first).to_be_visible()
            for window in ["24h", "48h", "7d"]:
                await page.get_by_role("tab", name=window, exact=True).click()
                await expect(
                    page.get_by_role("tab", name=window, exact=True)
                ).to_have_attribute("aria-selected", "true")
                await page.wait_for_timeout(300)
            await expect(
                page.locator(".directory-card .sparkline").first
            ).to_be_visible()
            await expect(
                page.get_by_text("历史样本不足", exact=True).first
            ).to_be_visible()
            await page.screenshot(
                path=str(snapshots / "trends-desktop.png"), full_page=True
            )
            checks["trend_windows_and_real_sparklines"] = True
            daily = reports["daily"]
            await page.get_by_role("link", name=daily["title"], exact=True).click()
            await expect(
                page.get_by_role("heading", name=daily["title"], exact=True).first
            ).to_be_visible()
            await expect(page.locator('[id^="digest-source-"]')).to_have_count(
                len(daily["sources"])
            )
            await page.screenshot(
                path=str(snapshots / "daily-report.png"), full_page=True
            )
            monthly = reports["monthly"]
            await page.goto(f"{BASE}/digest?kind=monthly&report={monthly['id']}")
            await expect(
                page.get_by_role("heading", name=monthly["title"], exact=True).first
            ).to_be_visible()
            await expect(
                page.locator(".report-analysis .recharts-wrapper").first
            ).to_be_visible()
            await expect(page.locator('[id^="digest-source-"]')).to_have_count(
                len(monthly["sources"])
            )
            checks["archive_navigation_and_monthly_charts"] = True
            await page.goto(BASE + "/login")
            await page.get_by_label("电子邮箱").fill(email)
            await page.get_by_label("密码（至少 10 个字符）").fill(password)
            await page.get_by_role("button", name="登录", exact=True).click()
            await page.wait_for_url(BASE + "/")
            await (
                page.locator(".sticky-aside")
                .get_by_role("button", name="订阅情报", exact=True)
                .click()
            )
            dialog = page.get_by_role("dialog")
            await expect(dialog).to_be_visible()
            await dialog.get_by_text("同时接收邮件简报", exact=True).click()
            await dialog.get_by_text("接收订阅矿种的价格预警邮件", exact=True).click()
            await dialog.get_by_role("button", name="保存订阅", exact=True).click()
            await expect(
                dialog.get_by_text("订阅偏好已保存", exact=False)
            ).to_be_visible()
            await page.keyboard.press("Escape")
            async with SessionFactory() as db:
                subscription = await db.scalar(
                    select(Subscription).where(Subscription.user_id == user_id)
                )
                assert subscription.email_enabled and subscription.price_alerts_enabled
            checks["email_and_price_warning_consent"] = True
            await page.get_by_role("link", name="消息中心", exact=True).first.click()
            await expect(
                page.get_by_role("heading", name="消息中心", exact=True)
            ).to_be_visible()
            await expect(page.locator(".notification-item")).to_have_count(
                payload["total"]
            )
            await page.get_by_role("button", name="全部标为已读", exact=True).click()
            await expect(
                page.get_by_role("heading", name="0 条未读", exact=True)
            ).to_be_visible()
            async with SessionFactory() as db:
                assert (
                    await db.scalar(
                        select(func.count())
                        .select_from(NoticeRead)
                        .where(NoticeRead.user_id == user_id)
                    )
                    == payload["total"]
                )
            await page.set_viewport_size({"width": 390, "height": 844})
            await page.wait_for_timeout(300)
            assert await page.evaluate(
                "document.documentElement.scrollWidth <= innerWidth"
            )
            await page.screenshot(
                path=str(snapshots / "inbox-mobile.png"), full_page=True
            )
            checks["owned_read_state_and_mobile_inbox"] = True
            await browser.close()
        assert not errors, errors
        checks["javascript_errors"] = errors
        ROOT.joinpath("docs/phase5-browser-verification.json").write_text(
            json.dumps(checks, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(json.dumps(checks, ensure_ascii=False))
    finally:
        async with SessionFactory.begin() as db:
            await db.execute(delete(User).where(User.id == user_id))


if __name__ == "__main__":
    asyncio.run(run())
