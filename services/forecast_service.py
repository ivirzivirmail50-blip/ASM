"""Manuscript Forecast — predict completion date based on writing pace.

Uses activity_log to compute writing velocity, then projects when the
manuscript will reach its total_word_goal.

Calculates:
- Current pace: avg words/day over last 7, 30, 90 days
- Words remaining to goal
- Estimated completion date at each pace
- Days remaining at each pace
- Projected completion % at key milestones (30/60/90 days from now)
- Best/worst case scenarios
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select, func

from core.cache import cache
from core.db import read_session
from models.activity import ActivityLog
from models.chapter import Chapter
from models.settings import Setting
from services._common import current_project_id

log = logging.getLogger("asm.forecast")

CACHE_TTL = 120  # 2 minutes


def _total_words() -> int:
    with read_session() as s:
        result = s.scalar(
            select(func.coalesce(func.sum(Chapter.word_count), 0)).where(
                Chapter.project_id == current_project_id(s)
            )
        )
        return int(result or 0)


def _total_goal() -> int:
    with read_session() as s:
        g = Setting.get(s, "total_word_goal", 80000)
        try:
            return int(g) if g else 80000
        except (ValueError, TypeError):
            return 80000


def _daily_goal() -> int:
    with read_session() as s:
        g = Setting.get(s, "daily_word_goal", 500)
        try:
            return int(g) if g else 500
        except (ValueError, TypeError):
            return 500


def _word_deltas_since(days: int) -> dict[str, int]:
    """Return {date_iso: word_count} for the past N days."""
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
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
        return {str(r[0]): max(0, int(r[1] or 0)) for r in rows}


def compute_forecast() -> dict[str, Any]:
    cache_key = "forecast:main"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    total_words = _total_words()
    total_goal = _total_goal()
    daily_goal = _daily_goal()
    words_remaining = max(0, total_goal - total_words)
    completion_pct = round(total_words / max(1, total_goal) * 100, 1)

    # Compute pace over different windows
    paces: dict[str, dict[str, Any]] = {}
    for window_days in [7, 30, 90]:
        deltas = _word_deltas_since(window_days)
        total_in_window = sum(deltas.values())
        writing_days = sum(1 for v in deltas.values() if v > 0)
        avg_per_day = total_in_window / max(1, window_days)  # avg over all days
        avg_per_writing_day = total_in_window / max(1, writing_days)  # avg per active day
        # Estimate completion
        if avg_per_day > 0:
            days_to_complete = words_remaining / avg_per_day
            est_date = date.today() + timedelta(days=days_to_complete)
        else:
            days_to_complete = None
            est_date = None
        paces[f"{window_days}d"] = {
            "window_days": window_days,
            "total_words": total_in_window,
            "writing_days": writing_days,
            "avg_per_day": round(avg_per_day, 1),
            "avg_per_writing_day": round(avg_per_writing_day, 1),
            "days_to_complete": round(days_to_complete, 0) if days_to_complete else None,
            "est_completion": est_date.isoformat() if est_date else None,
        }

    # Daily goal pace
    if daily_goal > 0:
        goal_days = words_remaining / daily_goal
        goal_est = date.today() + timedelta(days=goal_days)
    else:
        goal_days = None
        goal_est = None

    # Milestone projections (where will I be in 30/60/90 days at current 30d pace?)
    pace_30d = paces["30d"]["avg_per_day"]
    milestones: list[dict[str, Any]] = []
    for days in [30, 60, 90, 180]:
        projected_words = total_words + (pace_30d * days)
        projected_pct = round(projected_words / max(1, total_goal) * 100, 1)
        milestones.append({
            "days": days,
            "projected_words": int(projected_words),
            "projected_pct": projected_pct,
            "reaches_goal": projected_words >= total_goal,
        })

    result = {
        "total_words": total_words,
        "total_goal": total_goal,
        "words_remaining": words_remaining,
        "completion_pct": completion_pct,
        "daily_goal": daily_goal,
        "paces": paces,
        "daily_goal_forecast": {
            "days_to_complete": round(goal_days, 0) if goal_days else None,
            "est_completion": goal_est.isoformat() if goal_est else None,
        },
        "milestones": milestones,
        "on_track": completion_pct >= 50 and pace_30d >= daily_goal,
    }
    cache.set(cache_key, result, CACHE_TTL)
    return result
