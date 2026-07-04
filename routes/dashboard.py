"""Dashboard routes — Story Cockpit."""
from __future__ import annotations

from flask import Blueprint, render_template

from services import stats_service

bp = Blueprint("dashboard", __name__)


@bp.route("/")
def index():
    stats = stats_service.all_dashboard_stats()
    return render_template("dashboard.html", stats=stats, active_nav="dashboard")
