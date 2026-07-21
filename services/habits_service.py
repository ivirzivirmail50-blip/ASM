"""Writing Habit Insights — discover when you write best.

Analyzes activity_log to find patterns:
- Best day of week (Mon-Sun) by total words
- Best hour of day (0-23) by total words
- Heatmap: day-of-week × hour-of-day grid
- Writing frequency: days written vs days skipped (last 30/90 days)
- Streak analysis: longest streak, current streak
- Productivity ranking: which days of week produce most words

All from activity_log timestamps + word_count_delta.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select, func, extract

from core.cache import cache
from core.db import read_session
from models.activity import ActivityLog
from services._common import current_project_id

log = logging.getLogger("asm.habits")

CACHE_TTL = 120

DAYS_OF_WEEK = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
DAY_ABBR = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def compute_insights(*, days: int = 90) -> dict[str, Any]:
    cache_key = f"habits:{days}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)

    with read_session() as s:
        # Fetch all activity entries in window
        rows = list(s.execute(
            select(
                ActivityLog.timestamp,
                ActivityLog.word_count_delta,
            ).where(
                ActivityLog.entity_type == "chapter",
                ActivityLog.timestamp >= start,
                ActivityLog.timestamp < end,
            )
        ).all())

    if not rows:
        return {
            "days_analyzed": days,
            "total_entries": 0,
            "total_words": 0,
            "best_day_of_week": None,
            "best_hour": None,
            "heatmap": [[0] * 24 for _ in range(7)],  # 7×24 empty heatmap
            "heatmap_max": 1,
            "day_of_week_stats": [],
            "hour_stats": [],
            "frequency": {"writing_days": 0, "skipped_days": days, "total_days": days, "pct_writing_days": 0},
            "longest_streak": 0,
            "current_streak": 0,
        }

    # Build aggregates
    dow_words: dict[int, int] = {i: 0 for i in range(7)}  # 0=Monday
    dow_sessions: dict[int, int] = {i: 0 for i in range(7)}
    hour_words: dict[int, int] = {i: 0 for i in range(24)}
    hour_sessions: dict[int, int] = {i: 0 for i in range(24)}
    # Heatmap: [day][hour] = words
    heatmap: list[list[int]] = [[0] * 24 for _ in range(7)]
    # Daily totals for streak/frequency
    daily_words: dict[str, int] = {}

    total_words = 0
    for ts, wc in rows:
        if not ts or not wc:
            continue
        # Ensure timezone-aware
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        # Python weekday(): Monday=0, Sunday=6 — matches our array
        dow = ts.weekday()
        hour = ts.hour
        words = max(0, wc)
        dow_words[dow] += words
        dow_sessions[dow] += 1
        hour_words[hour] += words
        hour_sessions[hour] += 1
        heatmap[dow][hour] += words
        date_key = ts.date().isoformat()
        daily_words[date_key] = daily_words.get(date_key, 0) + words
        total_words += words

    # Best day of week
    best_dow = max(dow_words, key=dow_words.get) if any(dow_words.values()) else None
    # Best hour
    best_hour = max(hour_words, key=hour_words.get) if any(hour_words.values()) else None

    # Day-of-week stats
    dow_stats = [
        {
            "day": DAYS_OF_WEEK[i],
            "abbr": DAY_ABBR[i],
            "words": dow_words[i],
            "sessions": dow_sessions[i],
            "avg_per_session": round(dow_words[i] / max(1, dow_sessions[i]), 1),
        }
        for i in range(7)
    ]
    dow_stats.sort(key=lambda x: x["words"], reverse=True)

    # Hour stats (only hours with activity)
    hour_stats = [
        {
            "hour": h,
            "hour_label": f"{h:02d}:00",
            "words": hour_words[h],
            "sessions": hour_sessions[h],
        }
        for h in range(24) if hour_words[h] > 0
    ]
    hour_stats.sort(key=lambda x: x["words"], reverse=True)

    # Frequency
    writing_days = sum(1 for v in daily_words.values() if v > 0)
    total_days = days
    skipped_days = total_days - writing_days

    # Streaks
    longest_streak = 0
    current_streak = 0
    if daily_words:
        # Sort dates
        sorted_dates = sorted(daily_words.keys())
        # Compute longest streak
        streak = 0
        prev_date = None
        for d_str in sorted_dates:
            d = datetime.fromisoformat(d_str).date()
            if prev_date and (d - prev_date).days == 1:
                streak += 1
            else:
                streak = 1
            longest_streak = max(longest_streak, streak)
            prev_date = d
        # Current streak: walk backwards from today
        today = datetime.now(timezone.utc).date()
        d = today
        # Grace: if today has no activity, start from yesterday
        if daily_words.get(d.isoformat(), 0) == 0:
            d -= timedelta(days=1)
        current_streak = 0
        while daily_words.get(d.isoformat(), 0) > 0:
            current_streak += 1
            d -= timedelta(days=1)

    # Heatmap max for scaling
    heatmap_max = max(max(row) for row in heatmap) if any(any(row) for row in heatmap) else 1

    result = {
        "days_analyzed": days,
        "total_entries": len(rows),
        "total_words": total_words,
        "best_day_of_week": {
            "index": best_dow,
            "name": DAYS_OF_WEEK[best_dow] if best_dow is not None else None,
            "words": dow_words.get(best_dow, 0) if best_dow is not None else 0,
        } if best_dow is not None else None,
        "best_hour": {
            "hour": best_hour,
            "label": f"{best_hour:02d}:00" if best_hour is not None else None,
            "words": hour_words.get(best_hour, 0) if best_hour is not None else 0,
        } if best_hour is not None else None,
        "heatmap": heatmap,
        "heatmap_max": heatmap_max,
        "day_of_week_stats": dow_stats,
        "hour_stats": hour_stats,
        "frequency": {
            "writing_days": writing_days,
            "skipped_days": skipped_days,
            "total_days": total_days,
            "pct_writing_days": round(writing_days / max(1, total_days) * 100, 1),
        },
        "longest_streak": longest_streak,
        "current_streak": current_streak,
    }
    cache.set(cache_key, result, CACHE_TTL)
    return result
