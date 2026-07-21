"""Writing Habit Insights routes."""
from __future__ import annotations

import logging

from flask import Blueprint, jsonify, render_template, request

from services import habits_service as svc

log = logging.getLogger("asm.routes.habits")
bp = Blueprint("habits", __name__, url_prefix="/habits")


@bp.route("/")
def index():
    days = request.args.get("days", 90, type=int)
    insights = svc.compute_insights(days=days)
    return render_template(
        "habits.html",
        active_nav="habits",
        insights=insights,
        days=days,
    )


@bp.route("/api/insights")
def api_insights():
    days = request.args.get("days", 90, type=int)
    return jsonify({"ok": True, **svc.compute_insights(days=days)})
