"""Versioning service — wraps chapter/world snapshot decisions.

Cost-aware policy:
- Snapshots on: explicit Save, status change, re-upload, split/merge.
- Autosave: updates content only, no version row.
- Time-based: if (now - last_snapshot) >= interval AND content differs,
  the next explicit save creates a snapshot.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select

from core.db import read_session, write_transaction
from models.chapter import Chapter, ChapterVersion
from models.settings import Setting


def should_snapshot(
    *, last_snapshot_at: datetime | None, current_content: str,
    last_snapshot_content: str | None, interval_minutes: int = 15,
    explicit_save: bool = False,
) -> bool:
    """Decide whether to create a new snapshot."""
    if explicit_save:
        # Always snapshot on explicit save IF content differs from last snapshot
        return current_content != (last_snapshot_content or "")
    if last_snapshot_at is None:
        return True
    if current_content == (last_snapshot_content or ""):
        return False
    elapsed = datetime.now(timezone.utc) - last_snapshot_at
    return elapsed >= timedelta(minutes=interval_minutes)


def last_version_for_chapter(chapter_id: str) -> ChapterVersion | None:
    with read_session() as s:
        return s.scalar(
            select(ChapterVersion)
            .where(ChapterVersion.chapter_id == chapter_id)
            .order_by(ChapterVersion.version_number.desc())
        )
