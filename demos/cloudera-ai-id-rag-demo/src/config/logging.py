"""Logging configuration for the application."""

from __future__ import annotations

import collections
import datetime
import logging
import sys
import threading
from typing import TypedDict

from src.config.settings import settings

# Maximum number of log records kept in the in-memory ring buffer.
_BUFFER_SIZE = 500


class LogEntry(TypedDict):
    ts: str        # ISO-like timestamp string
    level: str     # DEBUG / INFO / WARNING / ERROR / CRITICAL
    logger: str    # logger name (abbreviated)
    message: str   # formatted message


class _MemoryHandler(logging.Handler):
    """Thread-safe ring buffer that stores the last _BUFFER_SIZE log records."""

    def __init__(self, maxlen: int = _BUFFER_SIZE) -> None:
        super().__init__()
        self._buf: collections.deque[LogEntry] = collections.deque(maxlen=maxlen)
        self._lock = threading.Lock()

    def emit(self, record: logging.LogRecord) -> None:
        try:
            ts = datetime.datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S")
            msg = record.getMessage()
            if record.exc_info:
                msg += "\n" + logging.Formatter().formatException(record.exc_info)
            entry: LogEntry = {
                "ts":      ts,
                "level":   record.levelname,
                "logger":  record.name.split(".")[-1],
                "message": msg,
            }
            with self._lock:
                self._buf.append(entry)
        except Exception:  # noqa: BLE001
            self.handleError(record)

    def entries(self, min_level: str = "DEBUG") -> list[LogEntry]:
        """Return a copy of the buffer, newest-first, filtered by minimum level."""
        level_no = getattr(logging, min_level.upper(), logging.DEBUG)
        with self._lock:
            return [
                e for e in reversed(self._buf)
                if getattr(logging, e["level"], 0) >= level_no
            ]


# Module-level singleton — created once by setup_logging(), read by get_log_entries().
_mem_handler: _MemoryHandler | None = None


def setup_logging() -> None:
    """Configure root logger with stdout stream + in-memory ring buffer."""
    global _mem_handler
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    fmt = "%(asctime)s [%(levelname)s] %(name)s — %(message)s"
    logging.basicConfig(stream=sys.stdout, level=level, format=fmt, force=True)

    # Attach the memory handler if not already present.
    root = logging.getLogger()
    if not any(isinstance(h, _MemoryHandler) for h in root.handlers):
        _mem_handler = _MemoryHandler()
        _mem_handler.setLevel(logging.DEBUG)
        root.addHandler(_mem_handler)


def get_log_entries(min_level: str = "DEBUG", limit: int = 200) -> list[LogEntry]:
    """Return recent log entries from the in-memory buffer, newest first."""
    if _mem_handler is None:
        return []
    return _mem_handler.entries(min_level)[:limit]


def get_logger(name: str) -> logging.Logger:
    """Return a named logger. Use module __name__ as the name."""
    return logging.getLogger(name)
