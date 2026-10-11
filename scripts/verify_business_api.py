"""Measure the running canonical API, Redis TTLs and actual publication gates."""

import argparse
import json
import math
import statistics
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    """Record warm-cache latency separately from database-backed cold requests."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-rate-limit", action="store_true")
    args = parser.parse_args()
    evidence: dict = {
        "checked_at": datetime.now(UTC).isoformat(),
        "base_url": "http://127.0.0.1:8001",
        "runtime": "local Windows API + PGlite + WSL Redis",
        "cache": {},
    }
    with httpx.Client(base_url=evidence["base_url"], timeout=20) as client:
        assert client.get("/health/ready").status_code == 200
        assert client.get("/docs").status_code == 200
        schema = client.get("/openapi.json").json()
        assert {} in schema["paths"]["/api/articles"]["get"]["security"]
        assert {} not in schema["paths"]["/api/open/articles"]["get"]["security"]
        assert client.get("/api/open/articles").status_code == 401
        feed = client.get("/api/articles", params={"page_size": 100}).json()
        assert feed["total"] > 0
        assert all(
            not a["url"].startswith("https://example.com/") for a in feed["items"]
        )
        evidence["published_articles"] = feed["total"]
        paths = [
            "/api/articles/" + feed["items"][0]["id"],
            "/api/articles/timeline?group_by=week",
            "/api/events",
            "/api/minerals",
            "/api/minerals/%E9%94%82/timeline",
            "/api/minerals/%E9%94%82/prices",
            "/api/minerals/%E9%94%82/policies",
            "/api/regions",
            "/api/regions/%E4%B8%AD%E5%9B%BD/articles",
            "/api/policies",
            "/api/search?q=%E7%A2%B3%E9%85%B8%E9%94%82",
            "/api/facets",
        ]
        evidence["routes"] = {path: client.get(path).status_code for path in paths}
        assert all(status == 200 for status in evidence["routes"].values())
        for path, ttl in [
            ("/api/articles/hot", 300),
            ("/api/trends/hot-minerals", 1800),
            ("/api/trends/price-alerts", 1800),
            ("/api/trends/policy-updates", 1800),
            ("/api/digest/daily", 3600),
            ("/api/digest/weekly", 3600),
            ("/api/digest/monthly", 3600),
        ]:
            start = time.perf_counter()
            response = client.get(path)
            cold_ms = (time.perf_counter() - start) * 1000
            response.raise_for_status()
            timings = []
            for _ in range(20):
                start = time.perf_counter()
                response = client.get(path)
                timings.append((time.perf_counter() - start) * 1000)
                response.raise_for_status()
                assert response.headers["X-Cache"] == "HIT"
                assert 0 < int(response.headers["X-Cache-TTL"]) <= ttl
            p95 = sorted(timings)[math.ceil(len(timings) * 0.95) - 1]
            evidence["cache"][path] = {
                "samples": len(timings),
                "first_ms": round(cold_ms, 2),
                "p50_ms": round(statistics.median(timings), 2),
                "p95_ms": round(p95, 2),
                "ttl_seconds": ttl,
                "cache": "HIT",
            }
            assert p95 < 200, (path, p95)
        if args.check_rate_limit:
            results = [client.get("/api/minerals").status_code for _ in range(125)]
            assert 429 in results and all(code in {200, 429} for code in results)
            evidence["slowapi_429"] = True
    output = ROOT / "docs" / "phase3-api-verification.json"
    output.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(evidence, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
