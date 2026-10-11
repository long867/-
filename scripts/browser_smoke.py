"""Local Edge browser QA with explicit synthetic API fixtures, never runtime mocks."""

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from playwright.sync_api import Route, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime.now(UTC).isoformat()
SOURCE_ID = "11111111-1111-4111-8111-111111111111"
SESSION_ID = "22222222-2222-4222-8222-222222222222"
USER_ID = "33333333-3333-4333-8333-333333333333"


def main() -> None:
    """Exercise desktop/mobile filters, prices, login, chat and administration."""
    source = {
        "id": SOURCE_ID,
        "name": "演示信源（虚构）",
        "url": "https://example.com/feed",
        "type": "rss",
        "category": "news",
        "language": "zh",
        "region": None,
        "authority_score": 5,
        "active": False,
        "fetch_interval": 900,
        "config_json": {},
    }
    articles = []
    for index, (mineral, region, title, category) in enumerate(
        [
            ("铜", "智利", "铜矿扩产项目进入新的评估阶段", "news"),
            ("锂", "澳大利亚", "关键矿产支持政策的情景分析", "policy"),
            ("稀土", "中国", "稀土产业与出口许可研究", "report"),
        ],
        1,
    ):
        summary = (
            f"【演示数据，非真实新闻】展示{region}{mineral}产业情报的"
            "聚合、标签与引用流程。"
        )
        articles.append(
            {
                "id": f"00000000-0000-4000-8000-{index:012d}",
                "source_id": SOURCE_ID,
                "title": "演示：" + title,
                "title_zh": "演示：" + title,
                "summary": summary,
                "summary_zh": summary,
                "content": summary + "\n原文保留数据日期与计量单位。",
                "content_zh": summary + "\n原文保留数据日期与计量单位。",
                "url": "https://example.com/demo",
                "published_at": NOW,
                "fetched_at": NOW,
                "category": category,
                "language": "zh",
                "quality_score": 80,
                "relevance_score": 90,
                "event_id": None,
                "is_translated": False,
                "minerals": [mineral],
                "regions": [region],
                "companies": [],
                "projects": [],
                "tags": ["演示数据"],
                "status": "published",
            }
        )
    messages = []
    errors: list[str] = []

    def handler(route: Route) -> None:
        parts = urlsplit(route.request.url)
        path = parts.path.removeprefix("/api/v1").removeprefix("/api")
        query = parse_qs(parts.query)
        data = None
        if path == "/articles":
            selected = articles
            for key, field in [
                ("mineral", "minerals"),
                ("region", "regions"),
                ("q", "title"),
                ("search", "title"),
            ]:
                if query.get(key):
                    selected = [
                        item for item in selected if query[key][0] in item[field]
                    ]
            data = {
                "items": selected,
                "total": len(selected),
                "page": 1,
                "page_size": 20,
            }
        elif path == "/articles/hot":
            data = articles
        elif path.startswith("/articles/"):
            data = articles[0]
        elif path in {"/sources", "/admin/sources"}:
            data = [source]
        elif path == "/facets":
            data = {
                "minerals": [
                    {"name": row["minerals"][0], "count": 1} for row in articles
                ],
                "regions": [
                    {"name": row["regions"][0], "count": 1} for row in articles
                ],
                "tags": [{"name": "演示数据", "count": 3}],
            }
        elif path == "/minerals":
            data = [
                {
                    "name": item["minerals"][0],
                    "article_count": 1,
                    "recent_count": 1,
                    "previous_count": 0,
                    "trend": "up",
                }
                for item in articles
            ]
        elif path == "/trends/hot-minerals":
            data = [
                {
                    "mineral": "铜",
                    "count": 1,
                    "previous_count": 0,
                    "growth_pct": None,
                    "is_new": True,
                }
            ]
        elif path in {"/trends/price-alerts", "/trends/policy-updates"}:
            data = []
        elif path == "/insights":
            data = {
                "window_hours": 24,
                "generated_at": NOW,
                "hotspots": [
                    {
                        "mineral": "铜",
                        "count": 1,
                        "previous_count": 0,
                        "growth_pct": None,
                        "is_new": True,
                    }
                ],
                "price_alerts": [],
            }
        elif path == "/prices" or path.endswith("/prices"):
            data = [
                {
                    "id": str(index),
                    "mineral": "铜",
                    "price": str(9000 + index * 40),
                    "unit": "吨",
                    "currency": "USD",
                    "date": f"2026-10-{index:02d}",
                    "source": "https://example.com/demo-prices",
                    "change_pct": None,
                }
                for index in range(1, 10)
            ]
        elif path == "/events":
            data = [
                {
                    "id": SESSION_ID,
                    "title_zh": "演示：铜矿扩产事件",
                    "summary_zh": articles[0]["summary"],
                    "last_updated_at": NOW,
                    "article_count": 1,
                    "minerals": ["铜"],
                    "regions": ["智利"],
                    "importance_score": 80,
                }
            ]
            data = {"items": data, "total": 1, "page": 1, "page_size": 20}
        elif path.startswith("/events/"):
            data = [articles[0]]
        elif path == "/auth/login":
            data = {
                "access_token": "browser-fixture-token",
                "user": {"id": USER_ID, "email": "admin@example.com", "is_admin": True},
            }
        elif path in {"/chat", "/chat/stream"} and route.request.method == "POST":
            question = route.request.post_data_json["question"]
            if messages:
                assert route.request.post_data_json["session_id"] == SESSION_ID
            quote = articles[0]["content"]
            citation = {
                "index": 1,
                "article_id": articles[0]["id"],
                "chunk_id": SOURCE_ID,
                "title": articles[0]["title"],
                "url": articles[0]["url"],
                "quote": quote,
                "start_char": 0,
                "end_char": len(quote),
                "published_at": NOW,
                "id": 1,
                "source_name": "演示信源（虚构）",
                "snippet": quote,
            }
            data = {
                "session_id": SESSION_ID,
                "message_id": str(len(messages) + 1),
                "answer": "演示回答：请核对以下原文证据。 [1]",
                "sources": [citation],
                "mode": "extractive",
            }
            messages.append(
                {
                    "id": data["message_id"],
                    "session_id": SESSION_ID,
                    "question": question,
                    "answer": data["answer"],
                    "sources_json": [citation],
                    "mode": "extractive",
                    "created_at": NOW,
                }
            )
            if path.endswith("/stream"):
                frames = [
                    ("status", {"phase": "retrieving"}),
                    ("sources", {"sources": [citation]}),
                    ("delta", {"text": data["answer"][:10]}),
                    ("delta", {"text": data["answer"][10:]}),
                    ("done", data),
                ]
                body = "".join(
                    f"event: {event}\ndata: {json.dumps(value, ensure_ascii=False)}\n\n"
                    for event, value in frames
                )
                route.fulfill(status=200, content_type="text/event-stream", body=body)
                return
        elif path == "/chat/sessions":
            data = (
                [{"id": SESSION_ID, "title": "演示咨询", "created_at": NOW}]
                if messages
                else []
            )
        elif path.startswith(("/chat/sessions/", "/chat/history/")):
            data = messages
        elif path.startswith("/chat/session/") and route.request.method == "DELETE":
            messages.clear()
            route.fulfill(status=204, body="")
            return
        elif path == "/admin/articles":
            data = articles
        elif path == "/admin/runs":
            data = []
        elif path == "/subscriptions/me":
            data = None
        elif path == "/subscriptions/feed":
            data = []
        elif path == "/policies":
            data = {"items": [], "total": 0, "page": 1, "page_size": 20}
        elif path == "/reports":
            data = []
        else:
            raise AssertionError(f"Unexpected fixture route: {path}")
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(data, ensure_ascii=False),
        )

    (ROOT / "artifacts").mkdir(exist_ok=True)
    with sync_playwright() as runtime:
        browser = runtime.chromium.launch(
            channel="msedge" if sys.platform == "win32" else None, headless=True
        )
        page = browser.new_page(viewport={"width": 1440, "height": 1050})
        page.route("**/api/**", handler)
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto("http://127.0.0.1:3000")
        page.wait_for_function(
            "document.querySelectorAll('.article-card').length === 3"
        )
        assert page.locator(".article-card").count() == 3
        page.screenshot(
            path=str(ROOT / "artifacts" / "frontend-desktop.png"), full_page=True
        )
        page.get_by_role("button", name="铜", exact=True).first.click()
        page.wait_for_function(
            "document.querySelectorAll('.article-card').length === 1"
        )
        page.get_by_role("button", name=articles[0]["title"], exact=True).click()
        page.get_by_text("原文保留数据日期与计量单位。").first.wait_for()
        page.get_by_role("tab", name="价格", exact=True).click()
        page.get_by_text("铜价格走势", exact=True).wait_for()
        assert page.get_by_text("现货 · 单一来源 · USD/吨", exact=True).is_visible()
        page.get_by_role("tab", name="事件时间线").click()
        page.get_by_role("button", name="演示：铜矿扩产事件", exact=True).wait_for()
        page.goto("http://127.0.0.1:3000/login")
        page.get_by_label("电子邮箱").fill("admin@example.com")
        page.get_by_label("密码（至少 10 个字符）").fill("fixture-password")
        page.get_by_role("button", name="登录", exact=True).click()
        page.wait_for_url("http://127.0.0.1:3000/")
        page.locator("nav").get_by_role("link", name="AI 咨询").click()
        page.get_by_label("你的矿产资源问题").fill("智利铜矿情况如何？")
        page.get_by_role("button", name="发送问题").click()
        page.get_by_text("演示回答：请核对以下原文证据。 [1]", exact=True).wait_for()
        page.get_by_role("button", name="查看来源 1").first.click()
        assert page.locator(".evidence blockquote").is_visible()
        assert (
            page.get_by_role("link", name="查看原文").get_attribute("href")
            == (articles[0]["url"])
        )
        page.get_by_label("你的矿产资源问题").fill("那对供给有什么影响？")
        page.get_by_role("button", name="发送问题").click()
        page.wait_for_function("document.querySelectorAll('.message').length === 2")
        page.get_by_role("button", name="发送问题").wait_for(state="visible")
        page.on("dialog", lambda dialog: dialog.accept())
        page.get_by_role("button", name="删除当前会话").click()
        page.wait_for_function("document.querySelectorAll('.message').length === 0")
        page.locator("nav").get_by_role("link", name="管理后台").click()
        page.get_by_role("heading", name="添加信源").wait_for()
        page.get_by_role("button", name="通过审核").first.wait_for()
        page.set_viewport_size({"width": 390, "height": 844})
        page.goto("http://127.0.0.1:3000/")
        page.locator(".article-card").first.wait_for()
        assert page.evaluate(
            "document.documentElement.scrollWidth <= window.innerWidth"
        )
        page.screenshot(
            path=str(ROOT / "artifacts" / "frontend-mobile.png"), full_page=True
        )
        browser.close()
    if errors:
        raise AssertionError(errors)
    print(
        "Browser smoke passed: desktop/mobile, filters, body, price chart, "
        "events, login, chat citations, admin."
    )


if __name__ == "__main__":
    main()
