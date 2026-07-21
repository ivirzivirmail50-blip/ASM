"""Scene Card Index routes."""
from __future__ import annotations

import logging

from flask import Blueprint, jsonify, render_template, request

from core.errors import AsmError
from services import scene_service as svc

log = logging.getLogger("asm.routes.scenes")
bp = Blueprint("scenes", __name__, url_prefix="/scenes")


@bp.route("/")
def index():
    chapter_id = request.args.get("chapter_id") or None
    mood = request.args.get("mood", "all")
    status = request.args.get("status", "all")
    cards = [svc.to_dict(c) for c in svc.list_cards(
        chapter_id=chapter_id, mood=mood, status=status,
    )]
    stats = svc.stats()
    return render_template(
        "scenes.html",
        active_nav="scenes",
        cards=cards,
        stats=stats,
        moods=svc.SCENE_MOODS,
        statuses=svc.SCENE_STATUSES,
        time_of_day=svc.TIME_OF_DAY,
        card_colors=svc.CARD_COLORS,
        current_mood=mood,
        current_status=status,
    )


@bp.route("/api/extract/<chapter_id>", methods=["POST"])
def api_extract_chapter(chapter_id: str):
    try:
        cards = svc.extract_from_chapter(chapter_id)
        return jsonify({"ok": True, "extracted": len(cards)})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


@bp.route("/api/extract-all", methods=["POST"])
def api_extract_all():
    try:
        result = svc.extract_all()
        return jsonify({"ok": True, **result})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


@bp.route("/api/list")
def api_list():
    cards = [svc.to_dict(c) for c in svc.list_cards(
        chapter_id=request.args.get("chapter_id"),
        mood=request.args.get("mood"),
        status=request.args.get("status"),
    )]
    return jsonify({"ok": True, "cards": cards})


@bp.route("/api/<card_id>", methods=["POST"])
def api_update(card_id: str):
    data = request.get_json(silent=True) or request.form
    try:
        svc.update_card(card_id, **data)
        return jsonify({"ok": True})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


@bp.route("/api/<card_id>/move/<new_chapter_id>", methods=["POST"])
def api_move(card_id: str, new_chapter_id: str):
    try:
        svc.move_to_chapter(card_id, new_chapter_id)
        return jsonify({"ok": True})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


@bp.route("/api/reorder", methods=["POST"])
def api_reorder():
    data = request.get_json(silent=True) or request.form
    card_ids = data.get("card_ids") or []
    if not isinstance(card_ids, list):
        return jsonify({"ok": False, "error": "card_ids must be a list"}), 400
    try:
        svc.reorder(card_ids)
        return jsonify({"ok": True})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


@bp.route("/api/<card_id>/delete", methods=["POST"])
def api_delete(card_id: str):
    try:
        svc.delete_card(card_id)
        return jsonify({"ok": True})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


@bp.route("/api/stats")
def api_stats():
    return jsonify({"ok": True, **svc.stats()})
