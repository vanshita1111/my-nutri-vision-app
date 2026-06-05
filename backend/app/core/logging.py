"""
Structured logging setup using Python's standard logging.
In production, logs are emitted as JSON for easy ingestion by CloudWatch / Datadog.
In development, logs are human-readable with colour.
"""

import logging
import sys
import json
from datetime import datetime, timezone

from app.config import settings


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log = {
            "ts":      datetime.now(timezone.utc).isoformat(),
            "level":   record.levelname,
            "logger":  record.name,
            "msg":     record.getMessage(),
        }
        if record.exc_info:
            log["exc"] = self.formatException(record.exc_info)
        if hasattr(record, "extra"):
            log.update(record.extra)
        return json.dumps(log, ensure_ascii=False)


class _DevFormatter(logging.Formatter):
    COLORS = {
        "DEBUG":    "\033[36m",
        "INFO":     "\033[32m",
        "WARNING":  "\033[33m",
        "ERROR":    "\033[31m",
        "CRITICAL": "\033[35m",
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, "")
        ts    = datetime.now(timezone.utc).strftime("%H:%M:%S")
        msg   = record.getMessage()
        if record.exc_info:
            msg += "\n" + self.formatException(record.exc_info)
        return f"{color}[{ts}] {record.levelname:<8} {record.name}: {msg}{self.RESET}"


def setup_logging() -> None:
    """Call once at application startup."""
    root = logging.getLogger()
    root.setLevel(logging.DEBUG if settings.DEBUG else logging.INFO)

    # Remove existing handlers
    root.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    if settings.APP_ENV == "production":
        handler.setFormatter(_JsonFormatter())
    else:
        handler.setFormatter(_DevFormatter())

    root.addHandler(handler)

    # Silence noisy third-party loggers
    for noisy in ("uvicorn.access", "sqlalchemy.engine", "httpx", "httpcore"):
        logging.getLogger(noisy).setLevel(
            logging.WARNING if not settings.DEBUG else logging.INFO
        )


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
