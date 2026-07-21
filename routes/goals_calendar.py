"""Word Count Goals Calendar routes."""
from __future__ import annotations

import logging
from datetime import date

from flask import Blueprint, jsonify, render_template, request

from services import goals_calendar_service as svc

log = logging.getLogger("asm.routes.goals_calendar")
bp = Blueprint("goals_calendar", __name__, url_prefix="/goals")


@bp.route("/")
def index():
    today = date.today()
    year = request.args.get("year", today.year, type=int)
    month = request.args.get("month", today.month, type=int)
    month_data = svc.get_month_calendar(year, month)
    year_data = svc.get_year_overview(year)
    progress = svc.get_current_progress()
    return render_template(
        "goals_calendar.html",
        active_nav="goals",
        month_data=month_data,
        year_data=year_data,
        progress=progress,
    )


@bp.route("/api/month/<int:year>/<int:month>")
def api_month(year: int, month: int):
    return jsonify({"ok": True, **svc.get_month_calendar(year, month)})


@bp.route("/api/year/<int:year>")
def api_year(year: int):
    return jsonify({"ok": True, **svc.get_year_overview(year)})


@bp.route("/api/progress")
def api_progress():
    return jsonify({"ok": True, **svc.get_current_progress()})
