"""Exercise the production frontend against actual persisted evidence."""

import json
import sys
from pathlib import Path

import httpx
from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:3000"


def main() -> None:
    """Verify responsive navigation, filters and charts without API fixtures."""
    with httpx.Client(base_url=BASE, timeout=30) as api:
        payload = api.get("/api/articles?page_size=100").raise_for_status().json()
        real_ids = {item["id"] for item in payload["items"]}
        assert payload["total"] > 10
        assert all("演示" not in a["source_name"] for a in payload["items"])
        assert all("example.com" not in a["url"] for a in payload["items"])
    errors: list[str] = []
    failures: list[str] = []
    checks: dict[str, object] = {}
    with sync_playwright() as runtime:
        browser = runtime.chromium.launch(
            channel="msedge" if sys.platform == "win32" else None, headless=True
        )
        page = browser.new_page(viewport={"width": 1440, "height": 1080})
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on(
            "response",
            lambda r: (
                failures.append(r.url) if "/api/" in r.url and r.status >= 400 else None
            ),
        )
        page.goto(BASE)
        expect(page.locator(".article-card").first).to_be_visible()
        page.screenshot(path=str(ROOT / "artifacts/frontend-dark-desktop.png"))
        assert (
            set(
                page.locator(".article-card").evaluate_all(
                    "cards=>cards.map(c=>c.dataset.articleId)"
                )
            )
            <= real_ids
        )
        while page.locator(".article-card").count() < payload["total"]:
            before = page.locator(".article-card").count()
            page.locator(".load-more").scroll_into_view_if_needed()
            expect(page.locator(".article-card")).not_to_have_count(before)
        expect(page.locator(".article-card")).to_have_count(payload["total"])
        checks["infinite_scroll"] = payload["total"]
        page.get_by_label("文章排序", exact=True).select_option("quality_score")
        page.get_by_label("搜索资讯", exact=True).fill("121000.00")
        expect(page.locator(".article-card")).to_have_count(1)
        assert "search=121000.00" in page.url
        assert "生意社" in page.locator(".article-card").inner_text()
        page.reload()
        expect(page.locator(".article-card")).to_have_count(1)
        page.get_by_label("收藏文章", exact=True).click()
        article_id = page.locator(".article-card").get_attribute("data-article-id")
        page.locator(".article-card h3 a").click()
        expect(page.locator(".reading-content")).to_be_visible()
        assert article_id in page.url
        page.goto(BASE + "/bookmarks")
        expect(page.locator(".article-card")).to_have_count(1)
        page.get_by_label("取消收藏", exact=True).click()
        expect(page.locator(".article-card")).to_have_count(0)
        checks["filters_reload_detail_bookmarks"] = True
        page.goto(BASE)
        page.get_by_label("切换亮色模式", exact=True).click()
        expect(page.locator("html")).to_have_attribute("data-theme", "light")
        page.reload()
        expect(page.locator("html")).to_have_attribute("data-theme", "light")
        page.screenshot(path=str(ROOT / "artifacts/frontend-light-desktop.png"))
        page.get_by_label("Switch to English", exact=True).click()
        expect(
            page.get_by_role("heading", name="Follow the resources.")
        ).to_be_visible()
        page.reload()
        expect(page.locator("html")).to_have_attribute("lang", "en")
        page.get_by_label("切换中文", exact=True).click()
        page.get_by_label("切换暗色模式", exact=True).click()
        checks["theme_language_persistence"] = True
        page.goto(BASE)
        rows = page.locator(".filter-row")
        rows.nth(0).get_by_role("button", name="锂", exact=False).click()
        rows.nth(0).get_by_role("button", name="金", exact=False).first.click()
        expect(page.locator(".article-card").first).to_be_visible()
        rows.nth(1).get_by_role("button", name="中国", exact=False).click()
        filtered = (
            httpx.get(
                BASE + "/api/articles",
                params=[
                    ("minerals", "锂"),
                    ("minerals", "金"),
                    ("regions", "中国"),
                    ("page_size", "100"),
                ],
            )
            .raise_for_status()
            .json()
        )
        while page.locator(".article-card").count() < filtered["total"]:
            before = page.locator(".article-card").count()
            page.locator(".load-more").scroll_into_view_if_needed()
            expect(page.locator(".article-card")).not_to_have_count(before)
        expect(page.locator(".article-card")).to_have_count(filtered["total"])
        assert set(
            page.locator(".article-card").evaluate_all(
                "cards=>cards.map(c=>c.dataset.articleId)"
            )
        ) == {item["id"] for item in filtered["items"]}
        assert "regions=" in page.url and page.url.count("minerals=") == 2
        checks["multi_select"] = True
        page.goto(BASE + "/minerals/" + "锂")
        expect(page.locator(".recharts-line-curve")).to_be_visible(timeout=20000)
        assert "碳酸锂" in page.locator("body").inner_text()
        page.screenshot(path=str(ROOT / "artifacts/frontend-lithium.png"))
        checks["real_price_chart"] = True
        page.goto(BASE + "/regions/" + "墨西哥")
        expect(page.locator(".leaflet-container")).to_be_visible(timeout=20000)
        expect(page.locator(".leaflet-tile-loaded").first).to_be_visible(timeout=20000)
        page.wait_for_function(
            "() => {const tiles=[...document.querySelectorAll('.leaflet-tile')];"
            "return tiles.length>0 && tiles.every(t=>t.complete && t.naturalWidth>0)}",
            timeout=20000,
        )
        page.wait_for_timeout(250)
        page.screenshot(path=str(ROOT / "artifacts/frontend-region-map.png"))
        checks["map"] = True
        page.goto(BASE + "/search?search=121000")
        expect(page.locator(".article-card")).to_have_count(1)
        expect(page.locator("mark").first).to_be_visible()
        checks["search_highlight"] = True
        page.goto(BASE + "/digest?kind=weekly")
        expect(page.locator(".digest-prose")).to_be_visible(timeout=20000)
        expect(page.locator(".recharts-bar").first).to_be_visible(timeout=20000)
        checks["weekly_digest"] = True
        for route in ["/policies", "/trends", "/events", "/chat", "/admin", "/about"]:
            response = page.goto(BASE + route)
            assert response and response.status == 200
            expect(page.locator("h1")).to_be_visible()
        page.goto(BASE)
        page.get_by_role("button", name="订阅情报", exact=True).first.click()
        expect(page.get_by_role("dialog")).to_be_visible()
        page.keyboard.press("Escape")
        expect(page.get_by_role("dialog")).to_have_count(0)
        checks["subscription_dialog"] = True
        for width in [390, 768]:
            page.set_viewport_size({"width": width, "height": 844})
            for route in [
                "/",
                "/minerals/锂",
                "/regions/墨西哥",
                "/digest?kind=weekly",
                "/search?search=121000",
            ]:
                page.goto(BASE + route)
                expect(page.locator("h1")).to_be_visible()
                page.wait_for_timeout(300)
                assert page.evaluate(
                    "document.documentElement.scrollWidth <= innerWidth"
                ), f"Overflow: {width} {route}"
            page.goto(BASE)
            page.get_by_label("打开导航", exact=True).click()
            expect(page.locator(".mobile-nav.open")).to_be_visible()
            page.locator(".mobile-nav.open").get_by_role(
                "link", name="矿种", exact=True
            ).click()
            expect(page).to_have_url(BASE + "/minerals")
        page.set_viewport_size({"width": 390, "height": 844})
        page.goto(BASE)
        page.screenshot(
            path=str(ROOT / "artifacts/frontend-dark-mobile.png"), full_page=True
        )
        checks["responsive"] = [390, 768, 1440]
        assert not errors, errors
        assert not failures, failures
        checks["page_errors"] = errors
        checks["api_errors"] = failures
        browser.close()
    (ROOT / "artifacts/frontend-live-smoke.json").write_text(
        json.dumps(checks, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(checks, ensure_ascii=False))


if __name__ == "__main__":
    main()
