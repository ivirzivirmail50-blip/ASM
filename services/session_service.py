"""Writing Session Timer service — Pomodoro-style focused writing sessions."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select, func

from core.db import read_session, write_transaction
from core.errors import NotFoundError, ValidationError
from models.session import WritingSession, SESSION_TYPES, SESSION_STATUSES
from models.chapter import Chapter
from services._common import current_project_id, new_uuid, now_utc

log = logging.getLogger("asm.sessions")


def _total_project_words() -> int:
    with read_session() as s:
        result = s.scalar(
            select(func.coalesce(func.sum(Chapter.word_count), 0)).where(
                Chapter.project_id == current_project_id(s)
            )
        )
        return int(result or 0)


def start_session(
    *, session_type: str = "pomodoro", target_minutes: int | None = None,
    chapter_id: str | None = None, notes: str = "",
) -> WritingSession:
    """Start a new writing session."""
    if session_type not in SESSION_TYPES:
        raise ValidationError(f"session_type must be one of {list(SESSION_TYPES)}.")
    # Determine target minutes
    if target_minutes is None:
        target_minutes = SESSION_TYPES[session_type]["minutes"] or 25
    if target_minutes < 1 or target_minutes > 600:
        raise ValidationError("target_minutes must be 1-600.")
    # Check no active session already exists
    existing = get_active_session()
    if existing:
        raise ValidationError(f"A session is already active (started {existing.started_at}). End it first.")
    sid = new_uuid()
    start_words = _total_project_words()
    with write_transaction() as s:
        sess = WritingSession(
            id=sid,
            project_id=current_project_id(s),
            session_type=session_type,
            target_minutes=target_minutes,
            status="active",
            started_at=now_utc(),
            elapsed_seconds=0,
            paused_seconds=0,
            word_count_start=start_words,
            word_count_end=start_words,
            words_written=0,
            chapter_id=chapter_id,
            notes=notes,
            created_at=now_utc(),
        )
        s.add(sess)
        s.flush()
        return sess


def get_active_session() -> WritingSession | None:
    with read_session() as s:
        return s.scalar(
            select(WritingSession).where(
                WritingSession.project_id == current_project_id(s),
                WritingSession.status.in_(["active", "paused"]),
            )
        )


def get_session(session_id: str) -> WritingSession:
    with read_session() as s:
        sess = s.get(WritingSession, session_id)
        if not sess:
            raise NotFoundError("Session not found.")
        return sess


def pause_session(session_id: str) -> WritingSession:
    with write_transaction() as s:
        sess = s.get(WritingSession, session_id)
        if not sess:
            raise NotFoundError("Session not found.")
        if sess.status != "active":
            raise ValidationError(f"Cannot pause session in '{sess.status}' state.")
        # Calculate elapsed time since last resume (or start)
        now = now_utc()
        started = sess.started_at.replace(tzinfo=timezone.utc) if sess.started_at else now
        elapsed_since_start = (now - started).total_seconds()
        # Add to existing elapsed_seconds
        sess.elapsed_seconds = (sess.elapsed_seconds or 0) + int(elapsed_since_start)
        sess.status = "paused"
        s.flush()
        return sess


def resume_session(session_id: str) -> WritingSession:
    with write_transaction() as s:
        sess = s.get(WritingSession, session_id)
        if not sess:
            raise NotFoundError("Session not found.")
        if sess.status != "paused":
            raise ValidationError(f"Cannot resume session in '{sess.status}' state.")
        # Reset started_at to now so JS timer counts from this moment
        sess.started_at = now_utc()
        sess.status = "active"
        s.flush()
        return sess


def end_session(session_id: str, *, status: str = "completed") -> WritingSession:
    """End a session. Computes final word count delta."""
    if status not in ("completed", "abandoned"):
        raise ValidationError("status must be completed or abandoned.")
    end_words = _total_project_words()
    with write_transaction() as s:
        sess = s.get(WritingSession, session_id)
        if not sess:
            raise NotFoundError("Session not found.")
        if sess.status in ("completed", "abandoned"):
            raise ValidationError("Session already ended.")
        now = now_utc()
        # If active, add the time since last resume/start to elapsed_seconds
        if sess.status == "active":
            started = sess.started_at.replace(tzinfo=timezone.utc) if sess.started_at else now
            elapsed_since_start = (now - started).total_seconds()
            sess.elapsed_seconds = (sess.elapsed_seconds or 0) + int(elapsed_since_start)
        sess.ended_at = now
        sess.word_count_end = end_words
        sess.words_written = max(0, end_words - sess.word_count_start)
        sess.status = status
        s.flush()
        return sess


def list_sessions(*, limit: int = 50) -> list[WritingSession]:
    with read_session() as s:
        return list(s.scalars(
            select(WritingSession).where(
                WritingSession.project_id == current_project_id(s)
            ).order_by(WritingSession.started_at.desc()).limit(limit)
        ))


def delete_session(session_id: str) -> None:
    with write_transaction() as s:
        sess = s.get(WritingSession, session_id)
        if sess:
            s.delete(sess)


def update_session(session_id: str, **fields: Any) -> WritingSession:
    with write_transaction() as s:
        sess = s.get(WritingSession, session_id)
        if not sess:
            raise NotFoundError("Session not found.")
        for k in ("notes", "session_type", "target_minutes"):
            if k in fields and fields[k] is not None:
                setattr(sess, k, fields[k])
        s.flush()
        return sess


def to_dict(sess: WritingSession) -> dict[str, Any]:
    return {
        "id": sess.id,
        "session_type": sess.session_type,
        "session_type_label": SESSION_TYPES.get(sess.session_type, {}).get("label", sess.session_type),
        "session_type_icon": SESSION_TYPES.get(sess.session_type, {}).get("icon", ""),
        "target_minutes": sess.target_minutes,
        "status": sess.status,
        "status_label": SESSION_STATUSES.get(sess.status, {}).get("label", sess.status),
        "status_icon": SESSION_STATUSES.get(sess.status, {}).get("icon", ""),
        "status_color": SESSION_STATUSES.get(sess.status, {}).get("color", "#94a3b8"),
        "started_at": sess.started_at.isoformat() if sess.started_at else None,
        "ended_at": sess.ended_at.isoformat() if sess.ended_at else None,
        "elapsed_seconds": sess.elapsed_seconds or 0,
        "paused_seconds": sess.paused_seconds or 0,
        "word_count_start": sess.word_count_start or 0,
        "word_count_end": sess.word_count_end or 0,
        "words_written": sess.words_written or 0,
        "chapter_id": sess.chapter_id,
        "notes": sess.notes or "",
        "wpm": round((sess.words_written or 0) / max(1, (sess.elapsed_seconds or 1) / 60), 1) if sess.elapsed_seconds else 0,
    }


def stats(*, days: int = 30) -> dict[str, Any]:
    """Aggregate stats for sessions in the past N days."""
    cutoff = now_utc() - timedelta(days=days)
    sessions = [s for s in list_sessions(limit=500)
                if s.started_at and _ensure_aware(s.started_at) >= cutoff]
    completed = [s for s in sessions if s.status == "completed"]
    total_minutes = sum((s.elapsed_seconds or 0) for s in completed) / 60
    total_words = sum((s.words_written or 0) for s in completed)
    return {
        "days": days,
        "total_sessions": len(sessions),
        "completed_sessions": len(completed),
        "total_minutes": round(total_minutes, 0),
        "total_words": total_words,
        "avg_wpm": round(total_words / max(1, total_minutes), 1) if total_minutes else 0,
        "avg_session_minutes": round(total_minutes / max(1, len(completed)), 0) if completed else 0,
    }


def _ensure_aware(dt: datetime) -> datetime:
    """Ensure a datetime is timezone-aware (UTC if naive)."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt
