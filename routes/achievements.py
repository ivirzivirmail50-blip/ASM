"""Achievements routes."""
from __future__ import annotations

import logging

from flask import Blueprint, jsonify, render_template

from services import achievement_service as svc

log = logging.getLogger("asm.routes.achievements")
bp = Blueprint("achievements", __name__, url_prefix="/achievements")


@bp.route("/")
def index():
    # Check and unlock any newly-qualified achievements
    svc.check_and_unlock()
    status = svc.get_status()
    return render_template(
        "achievements.html",
        active_nav="achievements",
        status=status,
        categories=svc.CATEGORIES,
    )


@bp.route("/api/check", methods=["POST"])
def api_check():
    result = svc.check_and_unlock()
    return jsonify({"ok": True, **result})


@bp.route("/api/status")
def api_status():
    return jsonify({"ok": True, **svc.get_status()})
