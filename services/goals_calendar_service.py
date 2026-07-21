"""Word Count Goals Calendar — visual calendar with daily/weekly/monthly goals.

Shows a month-grid calendar with each day colored by:
- Words written that day (heatmap intensity)
- Whether the daily goal was met (green checkmark)
- Whether the day is part of a streak

Also computes:
- Weekly progress (words this week vs weekly goal = daily_goal * 7)
- Monthly progress (words this month vs monthly goal = daily_goal * 30)
- Yearly progress (words this year vs yearly goal setting)
- Best day this month (highest word count)
- Average words per writing day
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

log = logging.getLogger("asm.goals_calendar")

CACHE_TTL = 60  # seconds


def _get_daily_goal(s) -> int:
    g = Setting.get(s, "daily_word_goal", 500)
    try:
        return int(g) if g else 500
    except (ValueError, TypeError):
        return 500


def _get_total_goal(s) -> int:
    g = Setting.get(s, "total_word_goal", 80000)
    try:
        return int(g) if g else 80000
    except (ValueError, TypeError):
        return 80000


def _word_deltas_for_range(start: date, end: date) -> dict[str, int]:
    """Return {date_iso: word_count} for the given date range."""
    start_dt = datetime(start.year, start.month, start.day, tzinfo=timezone.utc)
    end_dt = datetime(end.year, end.month, end.day, tzinfo=timezone.utc) + timedelta(days=1)
    with read_session() as s:
        rows = s.execute(
            select(
                func.date(ActivityLog.timestamp).label("d"),
                func.sum(ActivityLog.word_count_delta).label("wc"),
            ).where(
                ActivityLog.entity_type == "chapter",
                ActivityLog.timestamp >= start_dt,
                ActivityLog.timestamp < end_dt,
            ).group_by(func.date(ActivityLog.timestamp))
        ).all()
        return {str(r[0]): max(0, int(r[1] or 0)) for r in rows}


def _heat_level(words: int, goal: int) -> int:
    """0-4 intensity level based on words vs goal."""
    if words <= 0:
        return 0
    pct = words / max(1, goal)
    if pct < 0.25:
        return 1
    if pct < 0.5:
        return 2
    if pct < 1.0:
        return 3
    return 4


def get_month_calendar(year: int, month: int) -> dict[str, Any]:
    """Return a month-grid calendar with word counts per day."""
    cache_key = f"goals_calendar:{year}:{month}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    with read_session() as s:
        daily_goal = _get_daily_goal(s)

    # First day of month
    first = date(year, month, 1)
    # Last day of month
    if month == 12:
        last = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        last = date(year, month + 1, 1) - timedelta(days=1)

    # Get word deltas for the month (plus a few days before/after for week context)
    range_start = first - timedelta(days=first.weekday())  # Monday of first week
    range_end = last + timedelta(days=6 - last.weekday())  # Sunday of last week
    deltas = _word_deltas_for_range(range_start, range_end)

    # Build week rows (each row = 7 days, Monday-Sunday)
    weeks: list[list[dict[str, Any]]] = []
    d = range_start
    while d <= range_end:
        week: list[dict[str, Any]] = []
        for _ in range(7):
            iso = d.isoformat()
            words = deltas.get(iso, 0)
            week.append({
                "date": iso,
                "day": d.day,
                "in_month": d.month == month,
                "is_today": d == date.today(),
                "words": words,
                "goal_met": words >= daily_goal if words > 0 else False,
                "heat_level": _heat_level(words, daily_goal),
                "is_weekend": d.weekday() >= 5,
            })
            d += timedelta(days=1)
        weeks.append(week)

    # Month stats
    month_deltas = {k: v for k, v in deltas.items()
                    if k.startswith(f"{year:04d}-{month:02d}")}
    total_month = sum(month_deltas.values())
    writing_days = sum(1 for v in month_deltas.values() if v > 0)
    goal_met_days = sum(1 for v in month_deltas.values() if v >= daily_goal)
    best_day = max(month_deltas.items(), key=lambda x: x[1]) if month_deltas else None
    avg_per_writing_day = round(total_month / writing_days, 0) if writing_days else 0

    result = {
        "year": year,
        "month": month,
        "month_name": first.strftime("%B %Y"),
        "weeks": weeks,
        "daily_goal": daily_goal,
        "total_words": total_month,
        "writing_days": writing_days,
        "goal_met_days": goal_met_days,
        "best_day": {"date": best_day[0], "words": best_day[1]} if best_day else None,
        "avg_per_writing_day": int(avg_per_writing_day),
        "prev_month": (year - 1, 12) if month == 1 else (year, month - 1),
        "next_month": (year + 1, 1) if month == 12 else (year, month + 1),
    }
    cache.set(cache_key, result, CACHE_TTL)
    return result


def get_year_overview(year: int) -> dict[str, Any]:
    """Return a 12-month overview with totals."""
    cache_key = f"goals_year:{year}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    with read_session() as s:
        daily_goal = _get_daily_goal(s)
        total_goal = _get_total_goal(s)
        pid = current_project_id(s)
        # Total words this year
        start = datetime(year, 1, 1, tzinfo=timezone.utc)
        end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
        year_words = s.scalar(
            select(func.coalesce(func.sum(ActivityLog.word_count_delta), 0)).where(
                ActivityLog.entity_type == "chapter",
                ActivityLog.timestamp >= start,
                ActivityLog.timestamp < end,
            )
        ) or 0
        # Per-month breakdown
        rows = s.execute(
            select(
                func.strftime("%m", ActivityLog.timestamp).label("m"),
                func.sum(ActivityLog.word_count_delta).label("wc"),
            ).where(
                ActivityLog.entity_type == "chapter",
                ActivityLog.timestamp >= start,
                ActivityLog.timestamp < end,
            ).group_by(func.strftime("%m", ActivityLog.timestamp))
        ).all()
        by_month = {int(r[0]): max(0, int(r[1] or 0)) for r in rows}
        # Writing days this year
        days_rows = s.execute(
            select(func.date(ActivityLog.timestamp).label("d")).where(
                ActivityLog.entity_type == "chapter",
                ActivityLog.timestamp >= start,
                ActivityLog.timestamp < end,
            ).group_by(func.date(ActivityLog.timestamp))
        ).all()
        writing_days = len(days_rows)

    months = []
    for m in range(1, 13):
        words = by_month.get(m, 0)
        months.append({
            "month": m,
            "month_name": date(year, m, 1).strftime("%b"),
            "words": words,
            "heat_level": _heat_level(words, daily_goal * 30),  # monthly goal = daily*30
        })

    return {
        "year": year,
        "daily_goal": daily_goal,
        "total_goal": total_goal,
        "year_words": int(year_words),
        "writing_days": writing_days,
        "months": months,
        "year_goal_pct": round(int(year_words) / max(1, total_goal) * 100, 1),
        "avg_per_writing_day": round(int(year_words) / max(1, writing_days), 0) if writing_days else 0,
    }


def get_current_progress() -> dict[str, Any]:
    """Today/week/month/year progress against goals."""
    cache_key = "goals_current_progress"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    now = datetime.now(timezone.utc)
    today = now.date()
    monday = today - timedelta(days=today.weekday())
    month_start = date(today.year, today.month, 1)
    year_start = date(today.year, 1, 1)

    with read_session() as s:
        daily_goal = _get_daily_goal(s)
        total_goal = _get_total_goal(s)

    today_words = _word_deltas_for_range(today, today + timedelta(days=1)).get(today.isoformat(), 0)
    week_words = sum(_word_deltas_for_range(monday, today + timedelta(days=1)).values())
    month_words = sum(_word_deltas_for_range(month_start, today + timedelta(days=1)).values())
    year_words = sum(_word_deltas_for_range(year_start, today + timedelta(days=1)).values())

    result = {
        "today": {
            "words": today_words,
            "goal": daily_goal,
            "pct": round(today_words / max(1, daily_goal) * 100, 1),
            "goal_met": today_words >= daily_goal,
        },
        "week": {
            "words": week_words,
            "goal": daily_goal * 7,
            "pct": round(week_words / max(1, daily_goal * 7) * 100, 1),
            "days_elapsed": (today - monday).days + 1,
        },
        "month": {
            "words": month_words,
            "goal": daily_goal * 30,
            "pct": round(month_words / max(1, daily_goal * 30) * 100, 1),
        },
        "year": {
            "words": year_words,
            "goal": total_goal,
            "pct": round(year_words / max(1, total_goal) * 100, 1),
        },
    }
    cache.set(cache_key, result, CACHE_TTL)
    return result
