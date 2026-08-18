"""Structured logging helpers."""

from __future__ import annotations

import json
import logging
import sys
import time
from datetime import UTC, datetime
from typing import Any

_CONFIGURED = False


def setup_logging(level: int = logging.INFO) -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(_JsonFormatter())
    root = logging.getLogger("elitze")
    root.setLevel(level)
    root.addHandler(handler)
    root.propagate = False
    _CONFIGURED = True


def get_logger(name: str) -> _Logger:
    setup_logging()
    return _Logger(logging.getLogger(f"elitze.{name}"))


class _Logger:
    """Thin adapter routing ``fields=`` keyword into the record's ``extra``."""

    def __init__(self, logger: logging.Logger) -> None:
        self._l = logger

    @staticmethod
    def _split(kwargs: dict) -> dict:
        fields = kwargs.pop("fields", None)
        if fields is not None:
            kwargs["extra"] = {"fields": fields}
        return kwargs

    def debug(self, msg, *args, **kwargs) -> None:
        self._l.debug(msg, *args, **self._split(kwargs))

    def info(self, msg, *args, **kwargs) -> None:
        self._l.info(msg, *args, **self._split(kwargs))

    def warning(self, msg, *args, **kwargs) -> None:
        self._l.warning(msg, *args, **self._split(kwargs))

    def error(self, msg, *args, **kwargs) -> None:
        self._l.error(msg, *args, **self._split(kwargs))

    def exception(self, msg, *args, **kwargs) -> None:
        self._l.exception(msg, *args, **self._split(kwargs))


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.now(UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        extra = getattr(record, "fields", None)
        if isinstance(extra, dict):
            payload.update(extra)
        return json.dumps(payload, default=str)


def elapsed_since(start: float) -> float:
    return round(time.monotonic() - start, 4)
