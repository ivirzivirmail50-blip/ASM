"""Inspiration Hub routes — prompts, scenario generator, saved inspirations."""
from __future__ import annotations

import logging

from flask import Blueprint, jsonify, render_template, request

from core.errors import AsmError
from services import inspiration_service as svc

log = logging.getLogger("asm.routes.inspiration")
bp = Blueprint("inspiration", __name__, url_prefix="/inspiration")


@bp.route("/")
def index():
    daily = svc.daily_prompt()
    cats = svc.categories()
    saved = [svc.to_dict(r) for r in svc.list_saved()]
    return render_template(
        "inspiration.html",
        active_nav="inspiration",
        daily=daily,
        categories=cats,
        saved=saved,
    )


# --- JSON API ---------------------------------------------------------------

@bp.route("/api/daily")
def api_daily():
    return jsonify({"ok": True, "daily": svc.daily_prompt()})


@bp.route("/api/random")
def api_random():
    category = request.args.get("category")
    return jsonify({"ok": True, "prompt": svc.random_prompt(category)})


@bp.route("/api/scenario")
def api_scenario():
    return jsonify({"ok": True, "scenario": svc.random_scenario()})


@bp.route("/api/whatif")
def api_whatif():
    return jsonify({"ok": True, "prompt": svc.random_whatif()})


@bp.route("/api/prompts/<category>")
def api_prompts_for(category: str):
    return jsonify({"ok": True, "category": category,
                    "prompts": svc.prompts_for(category)})


@bp.route("/api/save", methods=["POST"])
def api_save():
    data = request.get_json(silent=True) or request.form
    try:
        rec = svc.save_inspiration(
            kind=data.get("kind", "prompt"),
            category=data.get("category", "general"),
            title=(data.get("title") or "").strip(),
            body=data.get("body", ""),
            meta=data.get("meta"),
        )
        return jsonify({"ok": True, "id": rec.id})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


@bp.route("/api/<inspiration_id>/pin", methods=["POST"])
def api_pin(inspiration_id: str):
    try:
        rec = svc.toggle_pin(inspiration_id)
        return jsonify({"ok": True, "pinned": bool(rec.pinned)})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


@bp.route("/api/<inspiration_id>/used", methods=["POST"])
def api_used(inspiration_id: str):
    try:
        rec = svc.mark_used(inspiration_id)
        return jsonify({"ok": True, "used": bool(rec.used)})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


@bp.route("/api/<inspiration_id>/delete", methods=["POST"])
def api_delete(inspiration_id: str):
    try:
        svc.delete_inspiration(inspiration_id)
        return jsonify({"ok": True})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code
