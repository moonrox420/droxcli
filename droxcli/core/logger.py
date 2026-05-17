"""
Structured logging with structlog if available, high-performance
JSON fallback otherwise. Never crashes.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from typing import Any, Dict, Protocol

try:
    import structlog  # type: ignore[import-not-found]
except ImportError:
    structlog = None  # type: ignore[assignment]

_STRUCTLOG_CONFIGURED = False
_STRUCTLOG_LOCK = threading.Lock()


class LoggerProtocol(Protocol):
    def info(self, event: str, **kwargs: Any) -> None: ...
    def error(self, event: str, **kwargs: Any) -> None: ...
    def warning(self, event: str, **kwargs: Any) -> None: ...
    def debug(self, event: str, **kwargs: Any) -> None: ...


class _FallbackLogger:
    """JSON logger with pid/thread awareness."""

    def __init__(self, name: str) -> None:
        self._logger = logging.getLogger(name)
        self._pid = os.getpid()

    def _log(self, level: int, event: str, fields: Dict[str, Any]) -> None:
        if not self._logger.isEnabledFor(level):
            return
        try:
            payload = {
                "ts": round(time.time(), 3),
                "level": logging.getLevelName(level),
                "pid": self._pid,
                "tid": threading.get_ident(),
                "event": event,
                **fields,
            }
            self._logger.log(level, json.dumps(payload, ensure_ascii=False))
        except Exception:
            self._logger.log(level, f"{event} {fields}")

    def info(self, event: str, **kw: Any) -> None:
        self._log(logging.INFO, event, kw)

    def error(self, event: str, **kw: Any) -> None:
        self._log(logging.ERROR, event, kw)

    def warning(self, event: str, **kw: Any) -> None:
        self._log(logging.WARNING, event, kw)

    def debug(self, event: str, **kw: Any) -> None:
        self._log(logging.DEBUG, event, kw)


def get_logger(name: str = "droxcli") -> LoggerProtocol:
    if structlog is not None:
        global _STRUCTLOG_CONFIGURED
        if not _STRUCTLOG_CONFIGURED:
            with _STRUCTLOG_LOCK:
                if not _STRUCTLOG_CONFIGURED:
                    structlog.configure(
                        processors=[
                            structlog.processors.add_log_level,
                            structlog.processors.TimeStamper(fmt="iso"),
                            structlog.processors.JSONRenderer(),
                        ]
                    )
                    _STRUCTLOG_CONFIGURED = True
        return structlog.get_logger(name)
    return _FallbackLogger(name)


logger = get_logger()
