"""Run integration checks against the separately named Compose database."""

import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote

from dotenv import dotenv_values


def main() -> None:
    """Keep database credentials out of command arguments and test output."""
    root = Path(__file__).resolve().parents[1]
    config = dotenv_values(root / "artifacts/compose-check/.env")
    username = quote(config.get("POSTGRES_USER") or "miningintel", safe="")
    password = quote(config["POSTGRES_PASSWORD"] or "", safe="")
    database = quote(config.get("POSTGRES_DB") or "miningintel", safe="")
    address = f"postgresql+asyncpg://{username}:{password}@127.0.0.1:55433/{database}"
    environment = os.environ.copy()
    environment.update(
        DATABASE_URL=address,
        TEST_DATABASE_URL=address,
        REDIS_URL="redis://127.0.0.1:6380/0",
        CELERY_BROKER_URL="redis://127.0.0.1:6380/1",
        CELERY_RESULT_BACKEND="redis://127.0.0.1:6380/2",
        LLM_API_KEY="",
        ML_ENABLED="false",
        APP_ENV="test",
    )
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--tb=short"],
        cwd=root / "backend",
        env=environment,
        check=False,
    )
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
