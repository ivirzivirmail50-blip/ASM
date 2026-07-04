"""Stats service: writing history, streaks, word counts, annual heatmap.

All public functions are cached with a 60s TTL via core.cache.
Cache is invalidated on any write operation (see services._common.log_activity).
"""
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select

from core.cache import cache, cached
from core.db import read_session
from models.activity import ActivityLog
from models.chapter import Chapter
from models.character import Character
from models.world import WorldEntry
from services._common import current_project_id

log = logging.getLogger("asm.stats")

STATS_CACHE_TTL = 60  # seconds


def _to_local(dt: datetime) -> datetime:
    """Convert UTC datetime to local (we use UTC for simplicity here)."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@cached("stats:overall_counts", ttl_seconds=STATS_CACHE_TTL)
def overall_counts() -> dict[str, int]:
    with read_session() as s:
        pid = current_project_id(s)
        chapters = s.scalar(
            select(func.count()).select_from(Chapter).where(
                Chapter.project_id == pid
            )
        ) or 0
        characters = s.scalar(
            select(func.count()).select_from(Character).where(
                Character.project_id == pid
            )
        ) or 0
        world_entries = s.scalar(
            select(func.count()).select_from(WorldEntry).where(
                WorldEntry.project_id == pid
            )
        ) or 0
        total_words = s.scalar(
            select(func.coalesce(func.sum(Chapter.word_count), 0)).where(
                Chapter.project_id == pid
            )
        ) or 0
        last_edit = s.scalar(
            select(func.max(Chapter.updated_at)).where(
                Chapter.project_id == pid
            )
        )
        return {
            "chapters": int(chapters),
            "characters": int(characters),
            "world_entries": int(world_entries),
            "total_words": int(total_words),
            "last_edit": last_edit.isoformat() if last_edit else None,
        }


@cached("stats:words_today", ttl_seconds=STATS_CACHE_TTL)
def words_today() -> int:
    now = datetime.now(timezone.utc)
    start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
    with read_session() as s:
        result = s.scalar(
            select(func.coalesce(func.sum(ActivityLog.word_count_delta), 0)).where(
                ActivityLog.entity_type == "chapter",
                ActivityLog.timestamp >= start,
            )
        )
        return int(result or 0)


@cached("stats:words_this_week", ttl_seconds=STATS_CACHE_TTL)
def words_this_week() -> int:
    now = datetime.now(timezone.utc)
    # Monday of current week
    monday = now - timedelta(days=now.weekday())
    start = datetime(monday.year, monday.month, monday.day, tzinfo=timezone.utc)
    with read_session() as s:
        result = s.scalar(
            select(func.coalesce(func.sum(ActivityLog.word_count_delta), 0)).where(
                ActivityLog.entity_type == "chapter",
                ActivityLog.timestamp >= start,
            )
        )
        return int(result or 0)


@cached("stats:words_this_month", ttl_seconds=STATS_CACHE_TTL)
def words_this_month() -> int:
    now = datetime.now(timezone.utc)
    start = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
    with read_session() as s:
        result = s.scalar(
            select(func.coalesce(func.sum(ActivityLog.word_count_delta), 0)).where(
                ActivityLog.entity_type == "chapter",
                ActivityLog.timestamp >= start,
            )
        )
        return int(result or 0)


def daily_history(days: int = 30) -> list[dict]:
    """Daily word-count deltas for the past N days (newest last)."""
    cache_key = f"stats:daily_history:{days}"
    cached_val = cache.get(cache_key)
    if cached_val is not None:
        return cached_val
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=days - 1)
    start = datetime(start.year, start.month, start.day, tzinfo=timezone.utc)
    with read_session() as s:
        rows = s.execute(
            select(
                func.date(ActivityLog.timestamp).label("d"),
                func.sum(ActivityLog.word_count_delta).label("wc"),
            ).where(
                ActivityLog.entity_type == "chapter",
                ActivityLog.timestamp >= start,
            ).group_by(func.date(ActivityLog.timestamp))
        ).all()
        by_date = {str(r[0]): int(r[1] or 0) for r in rows}
        # Fill missing days with 0; only count positive deltas for writing
        out = []
        for i in range(days):
            d = (start + timedelta(days=i)).date()
            ds = d.isoformat()
            v = by_date.get(ds, 0)
            # Clamp to 0 — deletes shouldn't make "writing" negative
            out.append({"date": ds, "words": max(0, v)})
        cache.set(cache_key, out, STATS_CACHE_TTL)
        return out


def annual_heatmap(year: int | None = None) -> list[dict]:
    """GitHub-style 365-day contribution grid for the given year."""
    cache_key = f"stats:annual_heatmap:{year}"
    cached_val = cache.get(cache_key)
    if cached_val is not None:
        return cached_val
    now = datetime.now(timezone.utc)
    year = year or now.year
    start = datetime(year, 1, 1, tzinfo=timezone.utc)
    end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
    with read_session() as s:
        rows = s.execute(
            select(
                func.date(ActivityLog.timestamp).label("d"),
                func.sum(ActivityLog.word_count_delta).label("wc"),
            ).where(
                ActivityLog.timestamp >= start,
                ActivityLog.timestamp < end,
            ).group_by(func.date(ActivityLog.timestamp))
        ).all()
        by_date = {str(r[0]): max(0, int(r[1] or 0)) for r in rows}
        out = []
        d = start.date()
        while d < end.date():
            out.append({
                "date": d.isoformat(),
                "words": by_date.get(d.isoformat(), 0),
                "level": _heat_level(by_date.get(d.isoformat(), 0)),
            })
            d += timedelta(days=1)
        cache.set(cache_key, out, STATS_CACHE_TTL)
        return out


def _heat_level(v: int) -> int:
    """Map word count to 0-4 intensity level."""
    if v <= 0:
        return 0
    if v < 100:
        return 1
    if v < 300:
        return 2
    if v < 800:
        return 3
    return 4


@cached("stats:writing_streak", ttl_seconds=STATS_CACHE_TTL)
def writing_streak() -> int:
    """Count consecutive days (ending today) with positive word deltas."""
    history = daily_history(days=365)
    # Walk backwards from today
    streak = 0
    for entry in reversed(history):
        if entry["words"] > 0:
            streak += 1
        else:
            break
    return streak


def recent_activity(limit: int = 10) -> list[dict]:
    cache_key = f"stats:recent_activity:{limit}"
    cached_val = cache.get(cache_key)
    if cached_val is not None:
        return cached_val
    with read_session() as s:
        rows = s.scalars(
            select(ActivityLog).order_by(ActivityLog.timestamp.desc()).limit(limit)
        ).all()
        return [
            {
                "id": r.id,
                "entity_type": r.entity_type,
                "entity_id": r.entity_id,
                "entity_title": r.entity_title,
                "action": r.action,
                "word_count_delta": r.word_count_delta,
                "timestamp": r.timestamp.isoformat() if r.timestamp else None,
            }
            for r in rows
        ]
    cache.set(cache_key, result, STATS_CACHE_TTL)
    return result


@cached("stats:character_appearance_heatmap", ttl_seconds=STATS_CACHE_TTL)
def character_appearance_heatmap() -> list[dict]:
    """For each character, count chapters that link them."""
    import json
    with read_session() as s:
        chapters = s.scalars(
            select(Chapter).where(Chapter.project_id == current_project_id(s))
        ).all()
        characters = s.scalars(
            select(Character).where(
                Character.project_id == current_project_id(s)
            ).order_by(Character.name.asc())
        ).all()
        counts: dict[str, int] = defaultdict(int)
        for ch in chapters:
            try:
                ids = json.loads(ch.character_ids or "[]")
            except (json.JSONDecodeError, TypeError):
                ids = []
            for cid in ids:
                counts[cid] += 1
        return [
            {
                "id": c.id,
                "name": c.name,
                "role": c.role,
                "avatar_color": c.avatar_color or "#6366f1",
                "appearances": counts.get(c.id, 0),
            }
            for c in characters
        ]


def upcoming_deadlines(days: int = 7) -> list[dict]:
    """Plan items with deadlines in the next N days."""
    cache_key = f"stats:upcoming_deadlines:{days}"
    cached_val = cache.get(cache_key)
    if cached_val is not None:
        return cached_val
    from models.plan import Plan
    now = datetime.now(timezone.utc).date()
    end = now + timedelta(days=days)
    with read_session() as s:
        rows = s.scalars(
            select(Plan).where(
                Plan.project_id == current_project_id(s),
                Plan.deadline.is_not(None),
                Plan.deadline >= now,
                Plan.deadline <= end,
            ).order_by(Plan.deadline.asc())
        ).all()
        return [
            {
                "id": p.id, "title": p.title,
                "deadline": p.deadline.isoformat() if p.deadline else None,
                "status": p.status,
            }
            for p in rows
        ]
    cache.set(cache_key, result, STATS_CACHE_TTL)
    return result


@cached("stats:all_dashboard_stats", ttl_seconds=STATS_CACHE_TTL)
def all_dashboard_stats() -> dict[str, Any]:
    return {
        "counts": overall_counts(),
        "words_today": words_today(),
        "words_this_week": words_this_week(),
        "words_this_month": words_this_month(),
        "daily_history": daily_history(days=30),
        "annual_heatmap": annual_heatmap(),
        "streak": writing_streak(),
        "recent_activity": recent_activity(limit=10),
        "character_heatmap": character_appearance_heatmap(),
        "upcoming_deadlines": upcoming_deadlines(days=7),
    }
