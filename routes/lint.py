"""Story Lint route — AI-free automated consistency checks."""
from __future__ import annotations

import logging

from flask import Blueprint, render_template

from services import lint_service

log = logging.getLogger("asm.routes.lint")
bp = Blueprint("lint", __name__)


@bp.route("/lint")
def index():
    """Run Story Lint and show results."""
    result = lint_service.lint_all()
    return render_template("lint.html", result=result, active_nav="lint")
