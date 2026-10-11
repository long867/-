"""Prepare isolated Compose runtime validation without modifying the local .env."""

import shutil
from pathlib import Path


def main() -> None:
    """Use our built images and separate volumes, PostgreSQL port and gateway."""
    root = Path(__file__).resolve().parents[1]
    target = root / "artifacts/compose-check"
    target.mkdir(parents=True, exist_ok=True)
    shutil.copytree(root / "deploy", target / "deploy", dirs_exist_ok=True)
    text = (root / "artifacts/server.env").read_text(encoding="utf-8")
    text += (
        "\nGATEWAY_BIND=127.0.0.1\nGATEWAY_PORT=3032\n"
        "API_IMAGE=miningintel-api:phase6\n"
        "WORKER_IMAGE=miningintel-worker:phase6\n"
        "FRONTEND_IMAGE=miningintel-frontend:phase6\n"
        "BACKUP_IMAGE=miningintel-backup:phase6\n"
    )
    (target / ".env").write_text(text, encoding="utf-8")
    (target / "deploy/check.yml").write_text(
        "services:\n  postgres:\n    ports: ['127.0.0.1:55433:5432']\n"
        "  api:\n    ports: ['127.0.0.1:8002:8000']\n",
        encoding="utf-8",
    )
    shutil.copyfile(
        root / "artifacts/evidence-snapshot.json", target / "evidence-snapshot.json"
    )
    print("Prepared isolated Compose check; credentials withheld")


if __name__ == "__main__":
    main()
