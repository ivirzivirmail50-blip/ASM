"""Manuscript Forecast routes."""
from __future__ import annotations

import logging

from flask import Blueprint, jsonify, render_template

from services import forecast_service as svc

log = logging.getLogger("asm.routes.forecast")
bp = Blueprint("forecast", __name__, url_prefix="/forecast")


@bp.route("/")
def index():
    forecast = svc.compute_forecast()
    return render_template(
        "forecast.html",
        active_nav="forecast",
        forecast=forecast,
    )


@bp.route("/api/forecast")
def api_forecast():
    return jsonify({"ok": True, **svc.compute_forecast()})
