"""Character Arc Tracker routes."""
from __future__ import annotations

import logging

from flask import Blueprint, jsonify, render_template, request

from core.errors import AsmError
from services import character_service, character_arc_service as svc

log = logging.getLogger("asm.routes.character_arcs")
bp = Blueprint("character_arcs", __name__, url_prefix="/character-arcs")


@bp.route("/")
def index():
    characters = character_service.list_characters()
    # Convert to plain dicts for JSON serialization in template
    char_list = [{"id": c.id, "name": c.name, "role": c.role,
                  "avatar_color": c.avatar_color or "#6366f1"} for c in characters]
    arcs = [svc.to_dict(a) for a in svc.list_arcs()]
    stats = svc.stats()
    return render_template(
        "character_arcs.html",
        active_nav="character_arcs",
        characters=char_list,
        arcs=arcs,
        stats=stats,
        stage_statuses=svc.STAGE_STATUSES,
    )


@bp.route("/api/new", methods=["POST"])
def api_new():
    data = request.get_json(silent=True) or request.form
    try:
        arc = svc.create_arc(
            character_id=data.get("character_id", ""),
            arc_name=data.get("arc_name", ""),
            description=data.get("description", ""),
        )
        return jsonify({"ok": True, "id": arc.id})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


@bp.route("/api/<arc_id>", methods=["POST"])
def api_update(arc_id: str):
    data = request.get_json(silent=True) or request.form
    try:
        svc.update_arc(arc_id, **data)
        return jsonify({"ok": True})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


@bp.route("/api/<arc_id>/delete", methods=["POST"])
def api_delete(arc_id: str):
    try:
        svc.delete_arc(arc_id)
        return jsonify({"ok": True})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


@bp.route("/api/<arc_id>/stage", methods=["POST"])
def api_add_stage(arc_id: str):
    data = request.get_json(silent=True) or request.form
    try:
        arc = svc.add_stage(
            arc_id,
            name=data.get("name", ""),
            description=data.get("description", ""),
            status=data.get("status", "planned"),
        )
        return jsonify({"ok": True, "stages": svc.to_dict(arc)["stages"]})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


@bp.route("/api/<arc_id>/stage/<int:stage_idx>", methods=["POST"])
def api_update_stage(arc_id: str, stage_idx: int):
    data = request.get_json(silent=True) or request.form
    try:
        arc = svc.update_stage(arc_id, stage_idx, **data)
        return jsonify({"ok": True, "stages": svc.to_dict(arc)["stages"]})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


@bp.route("/api/<arc_id>/stage/<int:stage_idx>/delete", methods=["POST"])
def api_delete_stage(arc_id: str, stage_idx: int):
    try:
        arc = svc.remove_stage(arc_id, stage_idx)
        return jsonify({"ok": True, "stages": svc.to_dict(arc)["stages"]})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


@bp.route("/api/stats")
def api_stats():
    return jsonify({"ok": True, **svc.stats()})
