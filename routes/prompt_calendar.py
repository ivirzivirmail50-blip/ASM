"""Writing Prompts Calendar — daily prompt calendar view.

Reuses the existing inspiration_service (which has a deterministic daily
prompt based on date hash) but adds a calendar UI:
- Month grid showing the prompt category for each day
- Click a day to see the full prompt
- Navigate months
- Save any day's prompt to your inspirations
- Start a new chapter from any day's prompt

This is a thin layer over inspiration_service — no new model needed.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any

from flask import Blueprint, jsonify, render_template, request

from services import inspiration_service as insp

log = logging.getLogger("asm.routes.prompt_calendar")
bp = Blueprint("prompt_calendar", __name__, url_prefix="/prompt-calendar")


@bp.route("/")
def index():
    today = date.today()
    year = request.args.get("year", today.year, type=int)
    month = request.args.get("month", today.month, type=int)
    month_data = _build_month(year, month)
    today_prompt = insp.daily_prompt()
    categories = insp.categories()
    return render_template(
        "prompt_calendar.html",
        active_nav="prompt_calendar",
        month_data=month_data,
        today_prompt=today_prompt,
        inspiration_categories=[(c["key"], c) for c in categories],
    )


@bp.route("/api/month/<int:year>/<int:month>")
def api_month(year: int, month: int):
    return jsonify({"ok": True, **_build_month(year, month)})


@bp.route("/api/day/<date_str>")
def api_day(date_str: str):
    """Get the prompt for a specific date."""
    try:
        d = date.fromisoformat(date_str)
    except ValueError:
        return jsonify({"ok": False, "error": "Invalid date format. Use YYYY-MM-DD."}), 400
    from datetime import datetime, timezone
    dt = datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
    prompt = insp.daily_prompt(dt)
    return jsonify({"ok": True, "prompt": prompt})


def _build_month(year: int, month: int) -> dict[str, Any]:
    """Build a month grid with a prompt for each day."""
    from datetime import datetime, timezone
    first = date(year, month, 1)
    # Last day of month
    if month == 12:
        last = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        last = date(year, month + 1, 1) - timedelta(days=1)
    # Build weeks (Mon-Sun)
    range_start = first - timedelta(days=first.weekday())
    range_end = last + timedelta(days=6 - last.weekday())
    weeks: list[list[dict[str, Any]]] = []
    d = range_start
    while d <= range_end:
        week: list[dict[str, Any]] = []
        for _ in range(7):
            dt = datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
            prompt = insp.daily_prompt(dt)
            week.append({
                "date": d.isoformat(),
                "day": d.day,
                "in_month": d.month == month,
                "is_today": d == date.today(),
                "category": prompt["category"],
                "category_label": prompt["category_label"],
                "icon": prompt["icon"],
                "text": prompt["text"],
            })
            d += timedelta(days=1)
        weeks.append(week)
    return {
        "year": year,
        "month": month,
        "month_name": first.strftime("%B %Y"),
        "weeks": weeks,
        "prev_month": (year - 1, 12) if month == 1 else (year, month - 1),
        "next_month": (year + 1, 1) if month == 12 else (year, month + 1),
    }
