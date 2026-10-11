"""Verify real reports, cache hits and Celery execution without external delivery."""

import json
from datetime import UTC, datetime
from pathlib import Path
from statistics import median
from time import perf_counter

import httpx

from app.core.config import get_settings
from app.tasks.celery_app import celery_app
from app.tasks.insights import refresh_insights
from app.tasks.reports import generate_report


def main() -> None:
    """Exercise configured workers and persisted public reports; write evidence."""
    settings = get_settings()
    if settings.EMAIL_NOTIFICATIONS_ENABLED or settings.WEBHOOK_NOTIFICATIONS_ENABLED:
        raise RuntimeError("Disable external delivery before running this verification")
    output = {
        "verified_at": datetime.now(UTC).isoformat(),
        "timezone": celery_app.conf.timezone,
        "worker_ping": celery_app.control.ping(timeout=3),
        "schedules": {
            name: str(celery_app.conf.beat_schedule[name]["schedule"])
            for name in ("daily-brief", "weekly-brief", "monthly-brief")
        },
        "scheduled_report_tasks": {},
        "warm_cache": {},
        "external_delivery_enabled": False,
    }
    assert output["worker_ping"], "Insights worker must be running"
    for kind in ("daily", "weekly", "monthly"):
        task = generate_report.delay(kind)
        result = task.get(timeout=45)
        assert result["report_id"] and result["status"] in {"succeeded", "unchanged"}
        output["scheduled_report_tasks"][kind] = {
            "task_id": task.id,
            "result": result,
        }
    output["insights_refresh"] = refresh_insights.delay().get(timeout=20)
    with httpx.Client(base_url="http://127.0.0.1:8001/api", timeout=20) as client:
        for route in (
            "/trends/hot-minerals?window=24h",
            "/trends/price-alerts",
            "/trends/policy-updates",
            "/digest/daily?scope=previous",
        ):
            client.get(route).raise_for_status()
            elapsed = []
            for _ in range(8):
                started = perf_counter()
                response = client.get(route).raise_for_status()
                elapsed.append((perf_counter() - started) * 1000)
                assert response.headers.get("X-Cache") == "HIT", route
            output["warm_cache"][route] = {
                "median_ms": round(median(elapsed), 2),
                "max_ms": round(max(elapsed), 2),
                "ttl_seconds": int(response.headers["X-Cache-TTL"]),
                "samples": len(elapsed),
            }
        reports = client.get("/digest/reports?page_size=20").raise_for_status().json()
        assert reports["total"] >= 3
        output["archived_reports"] = []
        for item in reports["items"]:
            detail = (
                client.get(f"/digest/reports/{item['id']}").raise_for_status().json()
            )
            assert detail["scheduled"] and detail["analysis"]
            assert all(
                "example.com" not in source["url"] for source in detail["sources"]
            )
            output["archived_reports"].append(
                {"id": item["id"], "kind": item["kind"], "mode": detail["mode"]}
            )
    target = (
        Path(__file__).resolve().parents[1] / "docs/phase5-scheduling-verification.json"
    )
    target.write_text(
        json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(output, ensure_ascii=False))


if __name__ == "__main__":
    main()
