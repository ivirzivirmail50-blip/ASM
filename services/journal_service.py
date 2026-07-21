"""Daily Writing Journal service — track the writer's process day by day."""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select, func

from core.db import read_session, write_transaction
from core.errors import NotFoundError, ValidationError
from models.journal import JournalEntry, JOURNAL_MOODS
from services._common import current_project_id, dump_json, load_json, log_activity, new_uuid, now_utc

log = logging.getLogger("asm.journal")


def list_entries(*, limit: int = 100) -> list[JournalEntry]:
    """Return recent journal entries (newest first)."""
    with read_session() as s:
        return list(s.scalars(
            select(JournalEntry).where(
                JournalEntry.project_id == current_project_id(s)
            ).order_by(JournalEntry.entry_date.desc()).limit(limit)
        ))


def get_entry(entry_id: str) -> JournalEntry:
    with read_session() as s:
        e = s.get(JournalEntry, entry_id)
        if not e:
            raise NotFoundError("Journal entry not found.")
        return e


def get_by_date(entry_date: date) -> JournalEntry | None:
    with read_session() as s:
        return s.scalar(
            select(JournalEntry).where(
                JournalEntry.project_id == current_project_id(s),
                JournalEntry.entry_date == entry_date,
            )
        )


def get_or_create_today() -> JournalEntry:
    """Get today's journal entry, creating an empty one if missing."""
    today = date.today()
    existing = get_by_date(today)
    if existing:
        return existing
    return _create_empty(today)


def _create_empty(entry_date: date) -> JournalEntry:
    # Pull today's word goal from settings, and actual from stats
    from models.settings import Setting
    goal = 500
    with read_session() as s:
        g = Setting.get(s, "daily_word_goal", "500")
        try:
            goal = int(g)
        except (ValueError, TypeError):
            goal = 500
    # Get actual words written today from activity log
    actual = _words_for_date(entry_date)
    with write_transaction() as s:
        e = JournalEntry(
            id=new_uuid(),
            project_id=current_project_id(s),
            entry_date=entry_date,
            word_count_goal=goal,
            word_count_actual=actual,
            tags=dump_json([]),
            created_at=now_utc(),
            updated_at=now_utc(),
        )
        s.add(e)
        s.flush()
        return e


def _words_for_date(entry_date: date) -> int:
    """Sum word deltas from activity_log for the given date."""
    from models.activity import ActivityLog
    start = datetime(entry_date.year, entry_date.month, entry_date.day, tzinfo=timezone.utc)
    end = start + timedelta(days=1)
    with read_session() as s:
        result = s.scalar(
            select(func.coalesce(func.sum(ActivityLog.word_count_delta), 0)).where(
                ActivityLog.entity_type == "chapter",
                ActivityLog.timestamp >= start,
                ActivityLog.timestamp < end,
            )
        )
        return max(0, int(result or 0))


def create_or_update_for_date(
    entry_date: date, *,
    mood: str | None = None, energy: int | None = None,
    word_count_goal: int | None = None, word_count_actual: int | None = None,
    wins: str | None = None, struggles: str | None = None,
    intentions: str | None = None, gratitude: str | None = None,
    notes: str | None = None, tags: list[str] | None = None,
) -> JournalEntry:
    """Create a new entry or update the existing one for this date."""
    if mood and mood not in JOURNAL_MOODS:
        raise ValidationError(f"mood must be one of {list(JOURNAL_MOODS)}.")
    if energy is not None and not (1 <= energy <= 5):
        raise ValidationError("energy must be 1-5.")
    existing = get_by_date(entry_date)
    if existing:
        return update_entry(existing.id, mood=mood, energy=energy,
                            word_count_goal=word_count_goal,
                            word_count_actual=word_count_actual,
                            wins=wins, struggles=struggles,
                            intentions=intentions, gratitude=gratitude,
                            notes=notes, tags=tags)
    # Create new
    with write_transaction() as s:
        e = JournalEntry(
            id=new_uuid(),
            project_id=current_project_id(s),
            entry_date=entry_date,
            mood=mood,
            energy=energy,
            word_count_goal=word_count_goal,
            word_count_actual=word_count_actual,
            wins=wins or "",
            struggles=struggles or "",
            intentions=intentions or "",
            gratitude=gratitude or "",
            notes=notes or "",
            tags=dump_json(tags or []),
            created_at=now_utc(),
            updated_at=now_utc(),
        )
        s.add(e)
        log_activity(
            s, entity_type="journal", entity_id=e.id,
            entity_title=f"Journal: {entry_date.isoformat()}", action="created",
        )
        s.flush()
        return e


def update_entry(entry_id: str, **fields: Any) -> JournalEntry:
    with write_transaction() as s:
        e = s.get(JournalEntry, entry_id)
        if not e:
            raise NotFoundError("Journal entry not found.")
        for k in ("mood", "energy", "word_count_goal", "word_count_actual",
                  "wins", "struggles", "intentions", "gratitude", "notes"):
            if k in fields and fields[k] is not None:
                setattr(e, k, fields[k])
        if "tags" in fields:
            e.tags = dump_json(fields["tags"] or [])
        e.updated_at = now_utc()
        s.flush()
        return e


def delete_entry(entry_id: str) -> None:
    with write_transaction() as s:
        e = s.get(JournalEntry, entry_id)
        if e:
            s.delete(e)


def to_dict(e: JournalEntry) -> dict[str, Any]:
    goal_met = (e.word_count_actual or 0) >= (e.word_count_goal or 0) if e.word_count_goal else False
    return {
        "id": e.id,
        "entry_date": e.entry_date.isoformat() if e.entry_date else None,
        "mood": e.mood or "",
        "mood_label": JOURNAL_MOODS.get(e.mood or "", {}).get("label", e.mood or ""),
        "mood_icon": JOURNAL_MOODS.get(e.mood or "", {}).get("icon", ""),
        "mood_color": JOURNAL_MOODS.get(e.mood or "", {}).get("color", "#94a3b8"),
        "mood_score": JOURNAL_MOODS.get(e.mood or "", {}).get("score", 3),
        "energy": e.energy,
        "word_count_goal": e.word_count_goal,
        "word_count_actual": e.word_count_actual,
        "goal_met": goal_met,
        "goal_pct": round((e.word_count_actual or 0) / max(1, e.word_count_goal or 1) * 100, 1) if e.word_count_goal else 0,
        "wins": e.wins or "",
        "struggles": e.struggles or "",
        "intentions": e.intentions or "",
        "gratitude": e.gratitude or "",
        "notes": e.notes or "",
        "tags": load_json(e.tags, []),
        "created_at": e.created_at.isoformat() if e.created_at else None,
        "updated_at": e.updated_at.isoformat() if e.updated_at else None,
    }


def stats(*, days: int = 30) -> dict[str, Any]:
    """Aggregate stats for the past N days."""
    end = date.today()
    start = end - timedelta(days=days - 1)
    entries = []
    with read_session() as s:
        entries = list(s.scalars(
            select(JournalEntry).where(
                JournalEntry.project_id == current_project_id(s),
                JournalEntry.entry_date >= start,
                JournalEntry.entry_date <= end,
            ).order_by(JournalEntry.entry_date.asc())
        ))
    if not entries:
        return {
            "days": days, "entries_count": 0, "avg_mood_score": 0,
            "avg_energy": 0, "goal_met_count": 0, "total_words": 0,
            "streak": 0, "mood_distribution": {},
        }
    mood_scores = [JOURNAL_MOODS.get(e.mood or "", {}).get("score", 3) for e in entries if e.mood]
    energies = [e.energy for e in entries if e.energy]
    goal_met = sum(1 for e in entries if e.word_count_goal and (e.word_count_actual or 0) >= e.word_count_goal)
    total_words = sum(e.word_count_actual or 0 for e in entries)
    mood_dist: dict[str, int] = {}
    for e in entries:
        if e.mood:
            mood_dist[e.mood] = mood_dist.get(e.mood, 0) + 1
    # Compute current streak (consecutive days with an entry, ending today or yesterday)
    streak = 0
    today = date.today()
    entry_dates = {e.entry_date for e in entries}
    d = today
    # Allow streak to count if today has an entry OR yesterday does (grace period)
    if today not in entry_dates and (today - timedelta(days=1)) not in entry_dates:
        streak = 0
    else:
        if today not in entry_dates:
            d = today - timedelta(days=1)
        while d in entry_dates:
            streak += 1
            d -= timedelta(days=1)
    return {
        "days": days,
        "entries_count": len(entries),
        "avg_mood_score": round(sum(mood_scores) / len(mood_scores), 2) if mood_scores else 0,
        "avg_energy": round(sum(energies) / len(energies), 2) if energies else 0,
        "goal_met_count": goal_met,
        "total_words": total_words,
        "streak": streak,
        "mood_distribution": mood_dist,
        "date_range": [start.isoformat(), end.isoformat()],
    }
