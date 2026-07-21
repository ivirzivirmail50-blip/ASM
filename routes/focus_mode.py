"""Focus Mode Pro — distraction-free writing with ambient sounds, Pomodoro, and notification blocking."""
from __future__ import annotations
import logging
from flask import Blueprint, render_template, jsonify, request
from services import chapter_service, session_service

bp = Blueprint("focus_mode", __name__, url_prefix="/focus")
log = logging.getLogger("asm.routes.focus")


@bp.route("/")
def index():
    chapters, _ = chapter_service.list_chapters(per_page=10000)
    active_session = session_service.get_active_session()
    return render_template("focus_mode/index.html", active_nav="focus_mode",
                           chapters=chapters, active_session=active_session)


@bp.route("/api/session/start", methods=["POST"])
def api_start_session():
    data = request.get_json(silent=True) or request.form
    try:
        sess = session_service.start_session(
            session_type=data.get("session_type", "pomodoro"),
            target_minutes=int(data["target_minutes"]) if data.get("target_minutes") else None,
            chapter_id=data.get("chapter_id") or None,
        )
        return jsonify({"ok": True, "id": sess.id})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400


@bp.route("/api/session/end", methods=["POST"])
def api_end_session():
    data = request.get_json(silent=True) or request.form
    sess = session_service.get_active_session()
    if not sess:
        return jsonify({"ok": False, "error": "No active session"}), 400
    try:
        ended = session_service.end_session(sess.id, status=data.get("status", "completed"))
        return jsonify({"ok": True, "words_written": ended.words_written})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
