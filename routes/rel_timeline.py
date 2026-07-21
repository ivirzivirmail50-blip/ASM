"""Character Relationship Timeline routes."""
from __future__ import annotations

import logging

from flask import Blueprint, jsonify, render_template, request

from core.errors import AsmError
from services import rel_timeline_service as svc, character_service

log = logging.getLogger("asm.routes.rel_timeline")
bp = Blueprint("rel_timeline", __name__, url_prefix="/rel-timeline")


@bp.route("/")
def index():
    events = svc.list_events()
    matrix = svc.get_timeline_matrix()
    stats = svc.stats()
    characters = character_service.list_characters()
    # Convert to plain dicts for JSON serialization
    char_list = [{"id": c.id, "name": c.name, "role": c.role,
                  "avatar_color": c.avatar_color or "#6366f1"} for c in characters]
    return render_template(
        "rel_timeline.html",
        active_nav="rel_timeline",
        events=events,
        matrix=matrix,
        stats=stats,
        characters=char_list,
    )


@bp.route("/api/events")
def api_events():
    char_id = request.args.get("character_id")
    return jsonify({"ok": True, "events": svc.list_events(character_id=char_id)})


@bp.route("/api/add", methods=["POST"])
def api_add():
    data = request.get_json(silent=True) or request.form
    try:
        event = svc.add_timeline_event(
            from_character_id=data.get("from_character_id", ""),
            to_character_id=data.get("to_character_id", ""),
            relationship_type=data.get("relationship_type", ""),
            description=data.get("description", ""),
            is_bidirectional=bool(data.get("is_bidirectional")),
        )
        return jsonify({"ok": True, "event": event})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


@bp.route("/api/<rel_id>/delete", methods=["POST"])
def api_delete(rel_id: str):
    try:
        svc.remove_event(rel_id)
        return jsonify({"ok": True})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


@bp.route("/api/matrix")
def api_matrix():
    return jsonify({"ok": True, **svc.get_timeline_matrix()})


@bp.route("/api/stats")
def api_stats():
    return jsonify({"ok": True, **svc.stats()})
