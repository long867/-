"""Offline validation of deployment topology, dashboard contracts and CI mirror."""

import json
from pathlib import Path

import yaml


def main() -> None:
    """Check configuration contracts without exposing environment secrets."""
    root = Path(__file__).resolve().parents[1]
    compose = yaml.safe_load((root / "deploy/docker-compose.yml").read_text())
    required = {
        "api",
        "worker",
        "beat",
        "frontend",
        "postgres",
        "redis",
        "qdrant",
        "nginx",
        "prometheus",
        "grafana",
        "alertmanager",
        "backup",
    }
    assert required <= compose["services"].keys()
    assert "--queues=celery,nlp,insights" in compose["services"]["worker"]["command"]
    small = yaml.safe_load(
        (root / "deploy/docker-compose.small.yml").read_text(encoding="utf-8")
    )["services"]
    assert "--concurrency=1" in small["worker"]["command"]
    assert small["qdrant"]["profiles"] == ["vector"]
    for service in ("api", "worker", "beat"):
        assert small[service]["environment"]["ML_ENABLED"] == "false"
        assert small[service]["environment"]["QDRANT_URL"] == ""
        assert "mem_limit" in small[service]
    rules = yaml.safe_load((root / "deploy/alerts.yml").read_text(encoding="utf-8"))
    assert len(rules["groups"][0]["rules"]) >= 4
    dashboard = json.loads(
        (root / "deploy/grafana/dashboards/operations.json").read_text(encoding="utf-8")
    )
    assert len(dashboard["panels"]) >= 10
    assert all(
        panel["targets"][0]["expr"].startswith(("sum", "miningintel_", "histogram_"))
        for panel in dashboard["panels"]
    )
    assert (root / ".github/workflows/ci.yml").read_bytes() == (
        root / "deploy/.github/workflows/ci.yml"
    ).read_bytes()
    print(
        json.dumps(
            {
                "services": sorted(required),
                "alert_rules": len(rules["groups"][0]["rules"]),
                "dashboard_panels": len(dashboard["panels"]),
                "workflow_mirror": "identical",
            }
        )
    )


if __name__ == "__main__":
    main()
