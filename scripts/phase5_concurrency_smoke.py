"""Verify concurrent real API reads after a preview database restart."""

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

import httpx

from app.core.cache import invalidate_public_cache


async def main() -> None:
    """Exercise cold report/trend reads alongside article queries without fixtures."""
    paths = [
        "/api/articles?page_size=2",
        "/api/events?page_size=2",
        "/api/minerals",
        "/api/digest/daily?scope=previous",
        "/api/digest/weekly?scope=previous",
        "/api/digest/monthly?scope=previous",
        "/api/trends/hot-minerals?window=24h",
        "/api/trends/price-alerts",
    ]
    statuses = []
    async with httpx.AsyncClient(
        base_url="http://127.0.0.1:8001", timeout=30
    ) as client:
        for _ in range(3):
            await invalidate_public_cache()
            responses = await asyncio.gather(*(client.get(path) for path in paths * 2))
            for response in responses:
                response.raise_for_status()
                statuses.append(response.status_code)
        ready = (await client.get("/health/ready")).raise_for_status().json()
        articles = (
            (await client.get("/api/articles?page_size=1")).raise_for_status().json()
        )
        reports = (await client.get("/api/digest/reports")).raise_for_status().json()
    result = {
        "verified_at": datetime.now(UTC).isoformat(),
        "concurrency": len(paths) * 2,
        "rounds": 3,
        "requests": len(statuses),
        "all_statuses_200": all(status == 200 for status in statuses),
        "readiness": ready,
        "published_articles": articles["total"],
        "archived_reports": reports["total"],
        "uses_test_fixtures": False,
    }
    assert articles["total"] > 0 and reports["total"] >= 3
    target = (
        Path(__file__).resolve().parents[1]
        / "docs/phase5-concurrency-verification.json"
    )
    target.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
