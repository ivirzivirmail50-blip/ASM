"""Common service helpers (activity logging, JSON serialization, current project)."""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Iterable

from sqlalchemy.orm import Session

from core.db import read_session, write_transaction
from models.activity import ActivityLog, cap_activity_log
from models.settings import Setting

log = logging.getLogger("asm.services")


def new_uuid() -> str:
    return uuid.uuid4().hex


def current_project_id(session: Session) -> str:
    """Return the active project id from settings, defaulting to 'default'."""
    pid = Setting.get(session, "active_project_id", "default")
    return pid or "default"


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def load_json(value: str | None, default: Any = None) -> Any:
    if not value:
        return default if default is not None else []
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return default if default is not None else []


def dump_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def log_activity(
    session: Session,
    *,
    entity_type: str,
    entity_id: str,
    entity_title: str,
    action: str,
    word_count_delta: int = 0,
    details: dict | None = None,
    project_id: str | None = None,
) -> None:
    """Insert an activity log entry and cap the table.

    Must be called within an existing write transaction.
    Also invalidates the stats cache so dashboard reflects fresh data.
    """
    pid = project_id or current_project_id(session)
    entry = ActivityLog(
        project_id=pid,
        entity_type=entity_type,
        entity_id=entity_id,
        entity_title=(entity_title or "")[:500],
        action=action,
        word_count_delta=word_count_delta or 0,
        details=dump_json(details) if details else None,
        timestamp=now_utc(),
    )
    session.add(entry)
    session.flush()  # ensure id assigned
    cap_activity_log(session)
    # Invalidate stats cache so next read fetches fresh data
    try:
        from core.cache import cache
        cache.invalidate("stats:")
    except Exception:
        pass  # don't fail the write if cache invalidation fails
