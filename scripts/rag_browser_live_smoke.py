"""Check the actual web/API login, SSE and deletion without request fixtures."""

import asyncio
import json
import secrets
import sys
from pathlib import Path
from uuid import uuid4

from app.core.config import get_settings
from app.core.db import SessionFactory
from app.core.security import hash_password
from app.models import User
from playwright.async_api import async_playwright
from sqlalchemy import delete

ROOT = Path(__file__).resolve().parents[1]


async def run() -> None:
    """Create one temporary account, exercise the running UI, then remove it."""
    if get_settings().APP_ENV == "production":
        raise ValueError("Use live browser smoke only in a development database")
    user_id = uuid4()
    email = f"browser-{user_id}@example.com"
    password = secrets.token_urlsafe(24)
    artifacts = ROOT / "artifacts"
    artifacts.mkdir(exist_ok=True)
    try:
        async with SessionFactory.begin() as db:
            db.add(User(id=user_id, email=email, password_hash=hash_password(password)))
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(
                channel="msedge" if sys.platform == "win32" else None,
                headless=True,
            )
            try:
                page = await browser.new_page(viewport={"width": 1440, "height": 1000})
                errors: list[str] = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                await page.goto("http://127.0.0.1:3000/login")
                await page.get_by_label("电子邮箱").fill(email)
                await page.get_by_label("密码（至少 10 个字符）").fill(password)
                await page.get_by_role("button", name="登录", exact=True).click()
                await page.wait_for_url("http://127.0.0.1:3000/", timeout=30000)
                await page.get_by_role("link", name="AI 咨询", exact=True).click()
                await page.wait_for_url("**/chat")
                await page.get_by_role("textbox", name="你的矿产资源问题").fill(
                    "今天天气怎么样"
                )
                async with page.expect_response(
                    lambda response: response.url.endswith("/api/chat/stream"),
                    timeout=30000,
                ) as received:
                    await page.get_by_role("button", name="发送问题").click()
                response = await received.value
                assert response.status == 200
                assert "text/event-stream" in response.headers["content-type"]
                await page.get_by_text(
                    "根据现有资料，未找到相关信息", exact=True
                ).wait_for(timeout=30000)
                assert await page.locator(".evidence").count() == 0
                await page.get_by_role("textbox", name="你的矿产资源问题").fill(
                    "2026年10月9日生意社碳酸锂现货报价是多少？请给出币种和单位。"
                )
                async with page.expect_response(
                    lambda response: response.url.endswith("/api/chat/stream")
                ) as price_response:
                    await page.get_by_role("button", name="发送问题").click()
                price_stream = await price_response.value
                frames = (await asyncio.wait_for(price_stream.text(), 240)).split(
                    "\n\n"
                )
                done = next(
                    frame for frame in frames if frame.startswith("event: done")
                )
                answer = json.loads(done.split("data: ", 1)[1])
                (artifacts / "phase3-rag-answer.json").write_text(
                    json.dumps(answer, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                assert answer["sources"] and "121000" in answer["answer"], answer
                citation = page.get_by_role("button", name="查看来源 1").first
                await citation.wait_for(timeout=30000)
                await citation.click()
                await page.wait_for_function(
                    "() => !!document.querySelector('details.evidence[open]')"
                )
                original = page.locator("details.evidence[open]").get_by_role(
                    "link", name="查看原文"
                )
                assert (await original.get_attribute("href")).startswith(
                    "https://www.100ppi.com/"
                )
                await page.get_by_role("textbox", name="你的矿产资源问题").fill(
                    "那这个报价的币种和单位是什么？"
                )
                async with page.expect_response(
                    lambda response: response.url.endswith("/api/chat/stream")
                ) as followup_response:
                    await page.get_by_role("button", name="发送问题").click()
                followup_stream = await followup_response.value
                frames = (await asyncio.wait_for(followup_stream.text(), 240)).split(
                    "\n\n"
                )
                done = next(
                    frame for frame in frames if frame.startswith("event: done")
                )
                followup = json.loads(done.split("data: ", 1)[1])
                assert followup["session_id"] == answer["session_id"]
                assert followup["sources"], followup
                await page.screenshot(
                    path=artifacts / "rag-browser-live.png", full_page=True
                )
                page.on("dialog", lambda dialog: dialog.accept())
                await page.get_by_role("button", name="发送问题").wait_for()
                await page.get_by_role("button", name="删除当前会话").click()
                await page.get_by_text(
                    "根据现有资料，未找到相关信息", exact=True
                ).wait_for(state="detached")
                assert not errors, errors
                print(
                    json.dumps(
                        {
                            "runtime": "actual frontend and API; no mocked HTTP",
                            "login": True,
                            "sse": True,
                            "off_topic_insufficient": True,
                            "grounded_citation_card": True,
                            "answer_mode": answer["mode"],
                            "followup_mode": followup["mode"],
                            "followup_same_session": True,
                            "delete_session": True,
                            "javascript_errors": errors,
                            "temporary_user_removed": True,
                        },
                        ensure_ascii=False,
                        indent=2,
                    )
                )
            finally:
                await browser.close()
    finally:
        async with SessionFactory.begin() as db:
            await db.execute(delete(User).where(User.id == user_id))


if __name__ == "__main__":
    asyncio.run(run())
