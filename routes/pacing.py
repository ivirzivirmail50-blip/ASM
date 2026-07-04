"""Pacing analysis route."""
from __future__ import annotations

import logging

from flask import Blueprint, render_template

from services import pacing_service

log = logging.getLogger("asm.routes.pacing")
bp = Blueprint("pacing", __name__)


@bp.route("/pacing")
def index():
    """Show pacing analysis dashboard."""
    result = pacing_service.analyze_all()
    return render_template("pacing.html", result=result, active_nav="pacing")
