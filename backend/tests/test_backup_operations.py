"""Backup safeguards: failed dumps and unverifiable uploads never become successes."""

import importlib.util
from datetime import UTC, datetime
from pathlib import Path
from subprocess import CalledProcessError
from types import SimpleNamespace

import pytest

spec = importlib.util.spec_from_file_location(
    "backup_module", Path(__file__).resolve().parents[2] / "deploy/backup/backup.py"
)
backup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backup)


def test_disabled_backup_and_calendar_slot(monkeypatch):
    monkeypatch.setenv("BACKUP_ENABLED", "false")
    assert backup.run_backup() == {"status": "disabled"}
    slot = backup.next_run(datetime(2026, 10, 10, 20, tzinfo=UTC))
    assert slot.isoformat() == "2026-10-12T03:00:00+08:00"


def test_backup_rejects_plaintext_and_parent_prefix(monkeypatch):
    monkeypatch.setenv("BACKUP_ENABLED", "true")
    monkeypatch.setenv("BACKUP_S3_BUCKET", "test-bucket")
    monkeypatch.setenv("BACKUP_S3_ENDPOINT", "http://storage.example.com")
    with pytest.raises(ValueError, match="HTTPS"):
        backup.run_backup()
    monkeypatch.setenv("BACKUP_S3_ENDPOINT", "https://storage.example.com")
    monkeypatch.setenv("BACKUP_S3_PREFIX", "../foreign")
    with pytest.raises(ValueError, match="prefix"):
        backup.run_backup()


def test_failed_dump_is_removed_without_a_success_marker(tmp_path, monkeypatch):
    monkeypatch.setenv("BACKUP_ENABLED", "true")
    monkeypatch.setenv("BACKUP_S3_BUCKET", "test-bucket")
    monkeypatch.setenv("BACKUP_S3_ENDPOINT", "https://storage.example.com")
    monkeypatch.setenv("BACKUP_DIR", str(tmp_path))

    def fail(command, **kwargs):
        assert command[0] == "pg_dump" and kwargs["capture_output"]
        raise CalledProcessError(1, "pg_dump", stderr="secret-database-password")

    monkeypatch.setattr(backup.subprocess, "run", fail)
    with pytest.raises(CalledProcessError):
        backup.run_backup()
    assert not list(tmp_path.iterdir())


def test_corrupt_remote_upload_is_never_marked_successful(tmp_path, monkeypatch):
    import sys

    monkeypatch.setenv("BACKUP_ENABLED", "true")
    monkeypatch.setenv("BACKUP_S3_BUCKET", "test-bucket")
    monkeypatch.setenv("BACKUP_S3_ENDPOINT", "https://storage.example.com")
    monkeypatch.setenv("BACKUP_DIR", str(tmp_path))

    def dump(command, **kwargs):
        if command[0] == "pg_dump":
            Path(command[-1]).write_bytes(b"PGDMP" + b"a" * 1000)
        else:
            assert command[:2] == ["pg_restore", "--list"]

    uploads = []
    storage = SimpleNamespace(
        upload_file=lambda *args, **kwargs: uploads.append(args),
        head_object=lambda **kwargs: {
            "ContentLength": 1,
            "Metadata": {"sha256": "wrong"},
        },
    )
    monkeypatch.setattr(backup.subprocess, "run", dump)
    monkeypatch.setitem(
        sys.modules, "boto3", SimpleNamespace(client=lambda *args, **kwargs: storage)
    )
    monkeypatch.setitem(
        sys.modules, "botocore.config", SimpleNamespace(Config=lambda **kwargs: None)
    )
    with pytest.raises(ValueError, match="verification failed"):
        backup.run_backup()
    assert len(uploads) == 1 and not list(tmp_path.iterdir())
