"""Milestone Celebrations routes."""
from __future__ import annotations

import logging

from flask import Blueprint, jsonify, render_template

from services import milestone_service as svc

log = logging.getLogger("asm.routes.milestones")
bp = Blueprint("milestones", __name__, url_prefix="/milestones")


@bp.route("/")
def index():
    # Check and celebrate any newly-reached milestones
    result = svc.check_and_celebrate()
    return render_template(
        "milestones.html",
        active_nav="milestones",
        result=result,
    )


@bp.route("/api/check", methods=["POST"])
def api_check():
    result = svc.check_and_celebrate()
    return jsonify({"ok": True, **result})


@bp.route("/api/status")
def api_status():
    return jsonify({"ok": True, **svc.get_status()})
