"""JSON structured logging with request correlation."""

import json
import logging
import os
import re
import sys
import traceback
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

import structlog

from app.core.config import get_settings


def scrub(value):
    """Redact named credentials and URL query secrets recursively."""
    if isinstance(value, dict):
        return {
            key: "[redacted]"
            if re.search(
                r"password|secret|authorization|api.?key|access.?token", key, re.I
            )
            else scrub(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [scrub(item) for item in value]
    if isinstance(value, str):
        for secret in (
            get_settings().LLM_API_KEY,
            get_settings().SMTP_PASSWORD,
            get_settings().SECRET_KEY,
            get_settings().QDRANT_API_KEY,
            get_settings().SLACK_WEBHOOK_URL,
            get_settings().FEISHU_WEBHOOK_URL,
            get_settings().WECOM_WEBHOOK_URL,
        ):
            if secret.get_secret_value():
                value = value.replace(secret.get_secret_value(), "[redacted]")
        value = re.sub(r"(://)[^/\s:@]+:[^@\s]+@", r"\1[redacted]@", value)
        value = re.sub(r"(?i)Bearer\s+\S+", "Bearer [redacted]", value)
        return re.sub(
            r"(?i)([?&](?:key|token|signature|api_key|access_token)=)[^&\s]+",
            r"\1[redacted]",
            value,
        )
    return value


class JsonFormatter(logging.Formatter):
    """Emit JSON lines for standard and structured logs, including Celery logs."""

    def format(self, record: logging.LogRecord) -> str:
        """Keep stack locations without exception strings, SQL parameters or locals."""
        try:
            value = json.loads(record.getMessage())
            if not isinstance(value, dict):
                raise ValueError()
        except (ValueError, TypeError):
            value = {"event": record.getMessage()}
        from datetime import UTC, datetime

        value.setdefault("timestamp", datetime.now(UTC).isoformat())
        value.setdefault("level", record.levelname.lower())
        value["logger"] = record.name
        if record.exc_info:
            value["error_type"] = record.exc_info[0].__name__
            value["stack"] = [
                {
                    "file": Path(frame.filename).name,
                    "line": frame.lineno,
                    "function": frame.name,
                }
                for frame in traceback.extract_tb(record.exc_info[2])
            ]
        return json.dumps(scrub(value), ensure_ascii=False, default=str)


def safe_exception(logger, method_name, event_dict):
    """Turn structlog exception information into safe stack locations."""
    info = event_dict.pop("exc_info", None)
    if info:
        import sys

        info = sys.exc_info() if info is True else info
        if isinstance(info, BaseException):
            info = (type(info), info, info.__traceback__)
        if isinstance(info, tuple) and info[0]:
            event_dict["error_type"] = info[0].__name__
            event_dict["stack"] = [
                {
                    "file": Path(frame.filename).name,
                    "line": frame.lineno,
                    "function": frame.name,
                }
                for frame in traceback.extract_tb(info[2])
            ]
    return event_dict


def configure_logging(level: str) -> None:
    """Configure standard library and structlog output."""
    root = logging.getLogger()
    root.setLevel(level)
    for handler in list(root.handlers):
        if getattr(handler, "miningintel", False):
            root.removeHandler(handler)
            handler.close()
    directory = Path(get_settings().LOG_DIR)
    directory.mkdir(parents=True, exist_ok=True)
    handlers = [
        logging.StreamHandler(sys.__stdout__ or sys.stdout),
        TimedRotatingFileHandler(
            directory / f"miningintel-{os.getpid()}.jsonl",
            when="midnight",
            utc=True,
            backupCount=get_settings().LOG_RETENTION_DAYS,
            encoding="utf-8",
        ),
    ]
    for handler in handlers:
        handler.miningintel = True
        handler.setFormatter(JsonFormatter())
        root.addHandler(handler)
    # Transport logs contain query strings; structured pipeline events omit them.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            safe_exception,
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
