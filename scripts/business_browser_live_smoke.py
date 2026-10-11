"""Verify real business pages and filters without HTTP fixtures or seeded news."""

import json
import sys
from pathlib import Path

import httpx
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    """Capture the actual desktop and mobile UI and verify its public provenance."""
    artifacts = ROOT / "artifacts"
    artifacts.mkdir(exist_ok=True)
    with httpx.Client(base_url="http://127.0.0.1:8001", timeout=20) as client:
        response = client.get("/api/articles", params={"page_size": 100})
        response.raise_for_status()
        feed = response.json()
        assert feed["total"] > 0
        assert all("演示信源" not in item["source_name"] for item in feed["items"])
        assert all(
            not item["url"].startswith("https://example.com/") for item in feed["items"]
        )
    errors: list[str] = []
    failures: list[str] = []
    with sync_playwright() as runtime:
        browser = runtime.chromium.launch(
            channel="msedge" if sys.platform == "win32" else None, headless=True
        )
        try:
            page = browser.new_page(viewport={"width": 1440, "height": 1000})
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.on(
                "response",
                lambda r: (
                    failures.append(r.url)
                    if "/api/" in r.url and r.status >= 400
                    else None
                ),
            )
            page.goto("http://127.0.0.1:3000/")
            page.locator(".article-card").first.wait_for()
            assert "演示信源（虚构）" not in page.locator("body").inner_text()
            page.get_by_label("每页条数").select_option("10")
            page.get_by_label("文章排序").select_option("quality_score")
            page.get_by_label("搜索资讯").fill("121000.00")
            page.wait_for_function(
                "document.querySelectorAll('.article-card').length === 1"
            )
            assert "生意社" in page.locator(".article-card").inner_text()
            page.get_by_label("搜索资讯").fill("")
            page.get_by_label("文章排序").select_option("published_at")
            page.wait_for_function(
                "document.querySelectorAll('.article-card').length === 10"
            )
            if feed["total"] > 10:
                first_title = page.locator(".article-card h3").first.inner_text()
                page.get_by_role("button", name="下一页", exact=True).click()
                page.wait_for_function(
                    "document.querySelector('.pagination')?.innerText.includes('2 /')"
                )
                page.wait_for_function(
                    "title => !!document.querySelector('.article-card h3') && "
                    "document.querySelector('.article-card h3').innerText !== title",
                    arg=first_title,
                )
                page.get_by_role("button", name="上一页", exact=True).click()
                page.wait_for_function(
                    "document.querySelectorAll('.article-card').length === 10"
                )
            page.screenshot(path=str(artifacts / "phase3-home.png"), full_page=True)
            page.get_by_role("tab", name="价格", exact=True).click()
            page.get_by_text(
                "碳酸锂（生意社现期表现货口径）", exact=False
            ).first.wait_for()
            assert page.locator("a[href*='100ppi.com']").count() > 0
            for path, heading in [("/minerals", "矿种情报"), ("/trends", "趋势洞察")]:
                page.goto("http://127.0.0.1:3000" + path)
                page.get_by_role("heading", name=heading).wait_for()
                page.wait_for_load_state("networkidle")
            for path in ("/events", "/policies", "/minerals/%E9%94%82"):
                page.goto("http://127.0.0.1:3000" + path)
                page.locator("main h1").wait_for()
                page.wait_for_load_state("networkidle")
                assert not page.locator("main [role=alert]").count(), (
                    path,
                    page.locator("main [role=alert]").all_text_contents(),
                    failures,
                )
            page.goto("http://127.0.0.1:3000/")
            page.get_by_role("tab", name="简报", exact=True).click()
            page.get_by_role("button", name="周报", exact=True).click()
            page.get_by_text("全球矿产资讯周报", exact=False).wait_for()
            assert page.locator("a[href*='100ppi.com']").count() > 0
            page.set_viewport_size({"width": 390, "height": 844})
            page.goto("http://127.0.0.1:3000/")
            page.locator(".article-card").first.wait_for()
            page.screenshot(path=str(artifacts / "phase3-mobile.png"), full_page=True)
            assert page.evaluate(
                "document.documentElement.scrollWidth <= innerWidth + 1"
            )
            assert not errors, errors
            assert not failures, failures
            evidence = {
                "mocked_http": False,
                "real_articles": feed["total"],
                "filters": True,
                "sorting": True,
                "pagination": feed["total"] > 10,
                "pages": ["/", "/minerals", "/events", "/policies", "/trends"],
                "price_source_link": True,
                "weekly_digest": True,
                "mobile_overflow": False,
                "javascript_errors": errors,
                "api_failures": failures,
            }
            (artifacts / "phase3-browser.json").write_text(
                json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            print(json.dumps(evidence, ensure_ascii=False, indent=2))
        finally:
            browser.close()


if __name__ == "__main__":
    main()
