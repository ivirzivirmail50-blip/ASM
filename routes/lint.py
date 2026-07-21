"""Story Lint route — AI-free automated consistency checks."""
from __future__ import annotations

import logging

from flask import Blueprint, render_template

from services import lint_service

log = logging.getLogger("asm.routes.lint")
bp = Blueprint("lint", __name__, url_prefix="/lint")


@bp.route("/")
def index():
    """Run Story Lint and show results."""
    result = lint_service.lint_all()
    return render_template("lint.html", result=result, active_nav="lint")


@bp.route("/style-coach/<chapter_id>")
def style_coach(chapter_id: str):
    """Get style-coach report for a specific chapter."""
    from services import lint_service
    result = lint_service.style_coach(chapter_id)
    return render_template("style_coach.html", result=result, active_nav="lint")
