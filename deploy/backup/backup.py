"""Daily verified PostgreSQL custom-format backups to S3 or OSS's S3 interface."""

import argparse
import hashlib
import json
import os
import subprocess
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4
from zoneinfo import ZoneInfo


def log(event: str, **fields) -> None:
    """Log operational metadata only; never emit connection strings or credentials."""
    print(
        json.dumps(
            {"event": event, "timestamp": datetime.now(UTC).isoformat(), **fields}
        ),
        flush=True,
    )


def run_backup() -> dict:
    """Validate a complete dump before upload and verify remote length/checksum."""
    if os.getenv("BACKUP_ENABLED", "false").lower() != "true":
        return {"status": "disabled"}
    bucket = os.environ["BACKUP_S3_BUCKET"]
    endpoint = os.getenv("BACKUP_S3_ENDPOINT") or None
    if endpoint and urlsplit(endpoint).scheme != "https":
        raise ValueError("Backup object storage requires HTTPS")
    prefix = os.getenv("BACKUP_S3_PREFIX", "miningintel/postgres").strip("/")
    if not prefix or ".." in prefix.split("/"):
        raise ValueError("Backup prefix must identify this application's directory")
    directory = Path(os.getenv("BACKUP_DIR", "/var/backups/miningintel")).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    target = directory / f"miningintel-{stamp}-{uuid4().hex[:8]}.dump"
    target.touch(mode=0o600, exist_ok=False)
    env = {**os.environ, "PGCONNECT_TIMEOUT": "15"}
    try:
        subprocess.run(
            [
                "pg_dump",
                "--format=custom",
                "--no-owner",
                "--no-acl",
                "--file",
                str(target),
            ],
            env=env,
            check=True,
            capture_output=True,
            timeout=1800,
        )
        subprocess.run(
            ["pg_restore", "--list", str(target)],
            check=True,
            capture_output=True,
            timeout=60,
        )
        digest = hashlib.sha256()
        with target.open("rb") as content:
            for block in iter(lambda: content.read(1024 * 1024), b""):
                digest.update(block)
        if target.stat().st_size < 100:
            raise ValueError("PostgreSQL dump is unexpectedly empty")
        import boto3
        from botocore.config import Config

        connection = boto3.client(
            "s3",
            endpoint_url=endpoint,
            region_name=os.getenv("AWS_DEFAULT_REGION", "us-east-1"),
            config=Config(
                signature_version="s3v4",
                request_checksum_calculation="when_required",
                response_checksum_validation="when_required",
                retries={"max_attempts": 3, "mode": "standard"},
                s3={
                    "addressing_style": os.getenv(
                        "BACKUP_S3_ADDRESSING_STYLE", "virtual"
                    )
                },
            ),
        )
        key = f"{prefix}/{stamp[:8]}/{target.name}"
        checksum = digest.hexdigest()
        extra = {
            "Metadata": {"sha256": checksum},
            "ContentType": "application/octet-stream",
        }
        if os.getenv("BACKUP_S3_ENCRYPTION"):
            extra["ServerSideEncryption"] = os.environ["BACKUP_S3_ENCRYPTION"]
        connection.upload_file(str(target), bucket, key, ExtraArgs=extra)
        head = connection.head_object(Bucket=bucket, Key=key)
        if (
            head["ContentLength"] != target.stat().st_size
            or head["Metadata"].get("sha256") != checksum
        ):
            raise ValueError("Uploaded backup verification failed")
        result = {
            "status": "uploaded",
            "key": key,
            "bytes": target.stat().st_size,
            "sha256": checksum,
        }
        (directory / "last-success.json").write_text(
            json.dumps({**result, "completed_at": datetime.now(UTC).isoformat()}),
            encoding="utf-8",
        )
        return result
    finally:
        # The cloud copy has an independently configured bucket lifecycle policy.
        # No delete/list privileges or automatic remote deletion are needed.
        target.unlink(missing_ok=True)


def next_run(now: datetime) -> datetime:
    """Return the next 03:00 local-calendar backup slot."""
    local = now.astimezone(ZoneInfo(os.getenv("BACKUP_TIMEZONE", "Asia/Shanghai")))
    slot = local.replace(hour=3, minute=0, second=0, microsecond=0)
    return slot if slot > local else slot + timedelta(days=1)


def main() -> None:
    """Run once or daemonize with bounded retries and a durable success marker."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--daemon", action="store_true")
    args = parser.parse_args()
    if not args.daemon:
        log("backup_complete", **run_backup())
        return
    while True:
        now = datetime.now(UTC)
        delay = (next_run(now) - now).total_seconds()
        log("backup_scheduled", next_run=next_run(now).isoformat())
        time.sleep(delay)
        for attempt in range(4):
            try:
                log("backup_complete", **run_backup())
                break
            except Exception as exc:
                log("backup_failed", attempt=attempt + 1, error_type=type(exc).__name__)
                if attempt < 3:
                    time.sleep(30 * 2**attempt)


if __name__ == "__main__":
    main()
