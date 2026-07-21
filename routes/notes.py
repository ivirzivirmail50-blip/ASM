"""Notes & Ideas Inbox routes."""
from __future__ import annotations

import logging

from flask import Blueprint, jsonify, render_template, request

from core.errors import AsmError
from services import note_service as svc

log = logging.getLogger("asm.routes.notes")
bp = Blueprint("notes", __name__, url_prefix="/notes")


@bp.route("/")
def index():
    category = request.args.get("category", "all")
    search = request.args.get("q", "")
    tag = request.args.get("tag", "")
    pinned_only = request.args.get("pinned") == "1"
    include_done = request.args.get("hide_done") != "1"
    notes = svc.list_notes(
        category=category if category != "all" else None,
        search=search or None,
        tag=tag or None,
        pinned_only=pinned_only,
        include_done=include_done,
    )
    note_dicts = [svc.to_dict(n) for n in notes]
    all_tags = svc.all_tags()
    return render_template(
        "notes.html",
        active_nav="notes",
        notes=note_dicts,
        categories=svc.NOTE_CATEGORIES,
        all_tags=all_tags,
        current_category=category,
        current_search=search,
        current_tag=tag,
        pinned_only=pinned_only,
        hide_done=not include_done,
    )


# --- JSON API ---------------------------------------------------------------

@bp.route("/api/list")
def api_list():
    notes = svc.list_notes(
        category=request.args.get("category"),
        search=request.args.get("q") or None,
        tag=request.args.get("tag") or None,
        pinned_only=request.args.get("pinned") == "1",
        include_done=request.args.get("hide_done") != "1",
    )
    return jsonify({"ok": True, "notes": [svc.to_dict(n) for n in notes]})


@bp.route("/api/new", methods=["POST"])
def api_new():
    data = request.get_json(silent=True) or request.form
    try:
        n = svc.create_note(
            title=(data.get("title") or "").strip(),
            body=data.get("body", ""),
            category=data.get("category", "idea"),
            tags=data.get("tags") or None,
            links=data.get("links") or None,
            pinned=bool(data.get("pinned")),
        )
        return jsonify({"ok": True, "id": n.id})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


@bp.route("/api/<note_id>", methods=["POST"])
def api_update(note_id: str):
    data = request.get_json(silent=True) or request.form
    try:
        svc.update_note(note_id, **data)
        return jsonify({"ok": True})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


@bp.route("/api/<note_id>/pin", methods=["POST"])
def api_pin(note_id: str):
    try:
        n = svc.toggle_pin(note_id)
        return jsonify({"ok": True, "pinned": bool(n.pinned)})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


@bp.route("/api/<note_id>/done", methods=["POST"])
def api_done(note_id: str):
    try:
        n = svc.toggle_done(note_id)
        return jsonify({"ok": True, "done": bool(n.done)})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


@bp.route("/api/<note_id>/link", methods=["POST"])
def api_link(note_id: str):
    data = request.get_json(silent=True) or request.form
    try:
        n = svc.add_link(
            note_id,
            entity_type=data.get("entity_type", ""),
            entity_id=data.get("entity_id", ""),
            entity_title=data.get("entity_title", ""),
        )
        return jsonify({"ok": True, "links": svc.to_dict(n)["links"]})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


@bp.route("/api/<note_id>/link/<entity_id>/delete", methods=["POST"])
def api_unlink(note_id: str, entity_id: str):
    try:
        n = svc.remove_link(note_id, entity_id)
        return jsonify({"ok": True, "links": svc.to_dict(n)["links"]})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


@bp.route("/api/<note_id>/promote/chapter", methods=["POST"])
def api_promote_chapter(note_id: str):
    try:
        ch_id = svc.promote_to_chapter(note_id)
        return jsonify({"ok": True, "chapter_id": ch_id})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


@bp.route("/api/<note_id>/promote/snippet", methods=["POST"])
def api_promote_snippet(note_id: str):
    try:
        snip_id = svc.promote_to_snippet(note_id)
        return jsonify({"ok": True, "snippet_id": snip_id})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


@bp.route("/api/<note_id>/promote/plan", methods=["POST"])
def api_promote_plan(note_id: str):
    try:
        plan_id = svc.promote_to_plan(note_id)
        return jsonify({"ok": True, "plan_id": plan_id})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


@bp.route("/api/<note_id>/delete", methods=["POST"])
def api_delete(note_id: str):
    try:
        svc.delete_note(note_id)
        return jsonify({"ok": True})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code
