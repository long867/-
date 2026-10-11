"""Verify admin forms and subscription persistence on the actual API."""

import asyncio
import json
import secrets
import sys
from uuid import uuid4

from app.core.config import get_settings
from app.core.db import SessionFactory
from app.core.security import hash_password
from app.models import Source, User
from playwright.async_api import async_playwright, expect
from sqlalchemy import delete


async def run() -> None:
    """Use one temporary staff account and source, then remove both."""
    if get_settings().APP_ENV == "production":
        raise ValueError("Browser QA requires a development database")
    user_id = uuid4()
    email = f"ui-admin-{user_id}@example.com"
    password = secrets.token_urlsafe(24)
    source_name = "UI QA " + uuid4().hex[:10]
    errors: list[str] = []
    try:
        async with SessionFactory.begin() as db:
            db.add(
                User(
                    id=user_id,
                    email=email,
                    password_hash=hash_password(password),
                    is_admin=True,
                )
            )
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                channel="msedge" if sys.platform == "win32" else None, headless=True
            )
            try:
                page = await browser.new_page(viewport={"width": 1440, "height": 1000})
                page.on("pageerror", lambda error: errors.append(str(error)))
                await page.goto("http://127.0.0.1:3000/login")
                await page.get_by_label("电子邮箱").fill(email)
                await page.get_by_label("密码（至少 10 个字符）").fill(password)
                await page.get_by_role("button", name="登录", exact=True).click()
                await page.wait_for_url("http://127.0.0.1:3000/")
                await page.get_by_role("link", name="管理", exact=True).click()
                await page.get_by_role("button", name="添加信源", exact=True).click()
                await page.get_by_label("名称", exact=True).fill(source_name)
                await page.get_by_label("公网 URL", exact=True).fill(
                    "https://resourceworld.com/feed/?qa=" + str(user_id)
                )
                await page.get_by_role("button", name="保存信源", exact=True).click()
                await expect(page.get_by_role("dialog")).to_have_count(0)
                await page.get_by_label("筛选信源").fill(source_name)
                await expect(page.locator(".admin-table tbody tr")).to_have_count(1)
                await page.get_by_label("编辑 " + source_name, exact=True).click()
                await expect(page.get_by_label("名称", exact=True)).to_have_value(
                    source_name
                )
                await page.get_by_label("权威性 1–10").fill("8")
                await page.get_by_role("button", name="保存信源", exact=True).click()
                await expect(page.get_by_role("dialog")).to_have_count(0)
                await expect(page.locator(".admin-table tbody")).to_contain_text("8/10")
                await page.get_by_role("button", name="停用", exact=True).click()
                await expect(
                    page.get_by_role("button", name="启用", exact=True)
                ).to_be_visible()
                await page.get_by_label("删除 " + source_name, exact=True).click()
                await page.get_by_role("button", name="确认删除", exact=True).click()
                await expect(page.get_by_role("dialog")).to_have_count(0)
                await expect(page.locator(".admin-table tbody tr")).to_have_count(0)
                for name in ["文章审核", "标签管理", "任务监控"]:
                    await page.get_by_role("tab", name=name, exact=True).click()
                    await expect(page.locator("h1")).to_be_visible()
                await page.get_by_label("任务 ID", exact=True).fill(str(uuid4()))
                await page.get_by_role("button", name="查询", exact=True).click()
                await expect(page.get_by_text("UNKNOWN", exact=True)).to_be_visible()
                # Save only this temporary account's subscription; no email opt-in.
                await page.get_by_role(
                    "button", name="订阅情报", exact=True
                ).last.click()
                await expect(page.get_by_role("dialog")).to_be_visible()
                await (
                    page.get_by_role("dialog")
                    .get_by_role("button", name="锂", exact=True)
                    .click()
                )
                await page.get_by_role("button", name="保存订阅", exact=True).click()
                await expect(
                    page.get_by_role("dialog").get_by_text(
                        "订阅偏好已保存", exact=False
                    )
                ).to_be_visible()
                await page.keyboard.press("Escape")
                await page.goto("http://127.0.0.1:3000/")
                assert not errors, errors
                print(
                    json.dumps(
                        {
                            "source_create_edit_pause_delete": True,
                            "admin_tabs": True,
                            "celery_real_state": True,
                            "subscription_saved": True,
                            "temporary_staff_source_removed": True,
                            "page_errors": errors,
                        },
                        ensure_ascii=False,
                    )
                )
            finally:
                await browser.close()
    finally:
        async with SessionFactory.begin() as db:
            await db.execute(delete(Source).where(Source.name == source_name))
            await db.execute(delete(User).where(User.id == user_id))


if __name__ == "__main__":
    asyncio.run(run())
