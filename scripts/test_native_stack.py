"""Run integration checks without competing with the live preview worker."""

import asyncio
import os
import sys
from pathlib import Path
from urllib.parse import quote
from uuid import uuid4

import asyncpg
from dotenv import dotenv_values


async def run_tests() -> int:
    """Create and remove only our unique scratch database; keep secrets private."""
    root = Path(__file__).resolve().parents[1]
    config = dotenv_values(root / "artifacts/compose-check/.env")
    raw_username = config.get("POSTGRES_USER") or "miningintel"
    raw_password = config["POSTGRES_PASSWORD"] or ""
    username = quote(raw_username, safe="")
    password = quote(raw_password, safe="")
    database = "miningintel_test_" + uuid4().hex
    address = f"postgresql+asyncpg://{username}:{password}@127.0.0.1:55433/{database}"
    environment = os.environ.copy()
    environment.update(
        DATABASE_URL=address,
        TEST_DATABASE_URL=address,
        REDIS_URL="redis://127.0.0.1:6380/8",
        CELERY_BROKER_URL="redis://127.0.0.1:6380/9",
        CELERY_RESULT_BACKEND="redis://127.0.0.1:6380/10",
        LLM_API_KEY="",
        ML_ENABLED="false",
        APP_ENV="test",
    )
    connection = await asyncpg.connect(
        host="127.0.0.1",
        port=55433,
        user=raw_username,
        password=raw_password,
        database="postgres",
    )
    created = False
    try:
        # The identifier contains only this fixed prefix and generated hex digits.
        await connection.execute(f'CREATE DATABASE "{database}"')
        created = True
        for arguments in (
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            [sys.executable, "-m", "pytest", "-q", "--tb=short"],
        ):
            process = await asyncio.create_subprocess_exec(
                *arguments, cwd=root / "backend", env=environment
            )
            returncode = await process.wait()
            if returncode:
                return returncode
        return 0
    finally:
        if created:
            await connection.execute(f'DROP DATABASE "{database}" WITH (FORCE)')
        await connection.close()


def main() -> None:
    """Run tests against native PostgreSQL with isolated database and Redis queues."""
    raise SystemExit(asyncio.run(run_tests()))


if __name__ == "__main__":
    main()
