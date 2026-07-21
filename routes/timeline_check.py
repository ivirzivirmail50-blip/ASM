"""Timeline Conflict Detection routes."""
from __future__ import annotations

import logging

from flask import Blueprint, jsonify, render_template, request

from services import timeline_check_service as svc

log = logging.getLogger("asm.routes.timeline_check")
bp = Blueprint("timeline_check", __name__, url_prefix="/timeline-check")


@bp.route("/")
def index():
    track = request.args.get("track", "all")
    result = svc.detect_conflicts(track=track if track != "all" else None)
    return render_template(
        "timeline_check.html",
        active_nav="timeline_check",
        result=result,
        current_track=track,
    )


@bp.route("/api/scan")
def api_scan():
    track = request.args.get("track")
    result = svc.detect_conflicts(track=track if track and track != "all" else None)
    return jsonify({"ok": True, **result})
