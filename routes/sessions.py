"""Writing Session Timer routes."""
from __future__ import annotations

import logging

from flask import Blueprint, jsonify, render_template, request

from core.errors import AsmError
from services import session_service as svc

log = logging.getLogger("asm.routes.sessions")
bp = Blueprint("sessions", __name__, url_prefix="/sessions")


@bp.route("/")
def index():
    active = svc.get_active_session()
    sessions = [svc.to_dict(s) for s in svc.list_sessions(limit=50)]
    stats = svc.stats(days=30)
    return render_template(
        "sessions.html",
        active_nav="sessions",
        active_session=svc.to_dict(active) if active else None,
        sessions=sessions,
        stats=stats,
        session_types=svc.SESSION_TYPES,
    )


@bp.route("/api/start", methods=["POST"])
def api_start():
    data = request.get_json(silent=True) or request.form
    try:
        sess = svc.start_session(
            session_type=data.get("session_type", "pomodoro"),
            target_minutes=int(data["target_minutes"]) if data.get("target_minutes") else None,
            chapter_id=data.get("chapter_id") or None,
            notes=data.get("notes", ""),
        )
        return jsonify({"ok": True, "id": sess.id, "session": svc.to_dict(sess)})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


@bp.route("/api/<session_id>/pause", methods=["POST"])
def api_pause(session_id: str):
    try:
        sess = svc.pause_session(session_id)
        return jsonify({"ok": True, "session": svc.to_dict(sess)})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


@bp.route("/api/<session_id>/resume", methods=["POST"])
def api_resume(session_id: str):
    try:
        sess = svc.resume_session(session_id)
        return jsonify({"ok": True, "session": svc.to_dict(sess)})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


@bp.route("/api/<session_id>/end", methods=["POST"])
def api_end(session_id: str):
    data = request.get_json(silent=True) or request.form
    status = data.get("status", "completed")
    try:
        sess = svc.end_session(session_id, status=status)
        return jsonify({"ok": True, "session": svc.to_dict(sess)})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


@bp.route("/api/<session_id>/delete", methods=["POST"])
def api_delete(session_id: str):
    try:
        svc.delete_session(session_id)
        return jsonify({"ok": True})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


@bp.route("/api/active")
def api_active():
    sess = svc.get_active_session()
    return jsonify({"ok": True, "session": svc.to_dict(sess) if sess else None})


@bp.route("/api/list")
def api_list():
    sessions = [svc.to_dict(s) for s in svc.list_sessions(limit=50)]
    return jsonify({"ok": True, "sessions": sessions})


@bp.route("/api/stats")
def api_stats():
    return jsonify({"ok": True, **svc.stats(days=30)})
