"""Structured logging via RotatingFileHandler.

Logs go to data/logs/asm.log (10 MB × 5 files). Format includes timestamp,
level, module, and request_id when available.
"""
from __future__ import annotations

import logging
import logging.handlers
import sys
import uuid
from contextvars import ContextVar
from typing import Optional

from config import Config

_request_id: ContextVar[Optional[str]] = ContextVar("request_id", default=None)


def set_request_id(rid: Optional[str] = None) -> str:
    """Set the request-scoped id; returns the id used."""
    rid = rid or uuid.uuid4().hex[:12]
    _request_id.set(rid)
    return rid


def get_request_id() -> Optional[str]:
    return _request_id.get()


class _RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        rid = get_request_id() or "-"
        record.request_id = rid
        return True


_format = (
    "%(asctime)s | %(levelname)-7s | %(name)s | req=%(request_id)s | %(message)s"
)


def configure_logging(level: int = logging.INFO) -> None:
    """Configure root + asm loggers with rotating file + console handlers."""
    Config.LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = Config.LOG_DIR / "asm.log"

    rid_filter = _RequestIdFilter()
    formatter = logging.Formatter(_format)

    file_handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    file_handler.addFilter(rid_filter)
    file_handler.setLevel(level)

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    console.addFilter(rid_filter)
    console.setLevel(level)

    root = logging.getLogger()
    # Avoid duplicate handlers on re-init.
    if not any(isinstance(h, logging.handlers.RotatingFileHandler)
               and getattr(h, "baseFilename", "") == str(log_file)
               for h in root.handlers):
        root.addHandler(file_handler)
    if not any(isinstance(h, logging.StreamHandler) and not
               isinstance(h, logging.handlers.RotatingFileHandler)
               for h in root.handlers):
        root.addHandler(console)
    root.setLevel(level)

    # Tone down noisy libs.
    logging.getLogger("werkzeug").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
