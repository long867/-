"""Validate install metadata and the offline privacy boundary in a real browser."""

import json
import sys
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    """Confirm APIs remain outside the service worker's static asset cache."""
    with sync_playwright() as p:
        browser = p.chromium.launch(
            channel="msedge" if sys.platform == "win32" else None, headless=True
        )
        context = browser.new_context()
        page = context.new_page()
        page.goto("http://127.0.0.1:3000/")
        page.wait_for_function("!!navigator.serviceWorker.controller")
        manifest = context.request.get(
            "http://127.0.0.1:3000/manifest.webmanifest"
        ).json()
        assert manifest["display"] == "standalone"
        assert {"192x192", "512x512"} <= {x["sizes"] for x in manifest["icons"]}
        for icon in manifest["icons"]:
            assert (
                context.request.get("http://127.0.0.1:3000" + icon["src"]).status == 200
            )
        # Trigger a genuine API request and assert its result is never cached.
        assert (
            context.request.get("http://127.0.0.1:3000/api/articles?page_size=1").status
            == 200
        )
        page.evaluate("fetch('/api/articles?page_size=1').then(r=>r.json())")
        cached = page.evaluate("""async()=>{
          const names=await caches.keys();
          const requests=await Promise.all(
            names.filter(n=>n.startsWith('miningintel-')).map(async n=>
              (await(await caches.open(n)).keys()).map(r=>r.url)
            )
          );
          return requests.flat();
        }""")
        assert all("/api/" not in url for url in cached)
        assert all(urlsplit(url).path not in {"/chat", "/login"} for url in cached)
        context.set_offline(True)
        page.goto("http://127.0.0.1:3000/chat?offline-test=1")
        expect(
            page.get_by_role("heading", name="暂时离线 / You're offline")
        ).to_be_visible()
        assert page.locator(".message").count() == 0
        context.set_offline(False)
        page.goto("http://127.0.0.1:3000/")
        expect(page.locator(".article-card").first).to_be_visible()
        result = {
            "manifest": True,
            "install_icons": True,
            "service_worker": True,
            "offline_fallback": True,
            "no_api_or_private_html_cache": True,
            "reconnect": True,
        }
        (ROOT / "artifacts/pwa-live-smoke.json").write_text(
            json.dumps(result, indent=2), encoding="utf-8"
        )
        print(json.dumps(result))
        browser.close()


if __name__ == "__main__":
    main()
