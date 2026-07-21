"""Character Mood Tracker routes."""
from __future__ import annotations

import logging

from flask import Blueprint, jsonify, render_template, request

from core.errors import AsmError
from services import char_mood_service as svc, character_service, chapter_service

log = logging.getLogger("asm.routes.char_mood")
bp = Blueprint("char_mood", __name__, url_prefix="/char-mood")


@bp.route("/")
def index():
    timeline = svc.get_timeline()
    return render_template(
        "char_mood.html",
        active_nav="char_mood",
        timeline=timeline,
        moods=svc.MOODS,
        intensities=svc.INTENSITIES,
    )


@bp.route("/api/set", methods=["POST"])
def api_set():
    data = request.get_json(silent=True) or request.form
    try:
        m = svc.set_mood(
            character_id=data.get("character_id", ""),
            chapter_id=data.get("chapter_id", ""),
            mood=data.get("mood", ""),
            intensity=data.get("intensity", "medium"),
            note=data.get("note", ""),
        )
        return jsonify({"ok": True, "id": m.id})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


@bp.route("/api/<mood_id>/delete", methods=["POST"])
def api_delete(mood_id: str):
    try:
        svc.delete_mood(mood_id)
        return jsonify({"ok": True})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


@bp.route("/api/timeline")
def api_timeline():
    char_id = request.args.get("character_id")
    return jsonify({"ok": True, **svc.get_timeline(character_id=char_id)})
