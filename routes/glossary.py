"""Glossary & Style Sheet routes."""
from __future__ import annotations

import logging

from flask import Blueprint, jsonify, render_template, request

from core.errors import AsmError
from services import glossary_service as svc

log = logging.getLogger("asm.routes.glossary")
bp = Blueprint("glossary", __name__, url_prefix="/glossary")


@bp.route("/")
def index():
    category = request.args.get("category", "all")
    entries = [svc.to_dict(e) for e in svc.list_entries(category=category if category != "all" else None)]
    return render_template(
        "glossary.html",
        active_nav="glossary",
        entries=entries,
        categories=svc.CATEGORIES,
        current_category=category,
    )


@bp.route("/scan")
def scan():
    chapter_id = request.args.get("chapter_id") or None
    result = svc.scan_chapters(chapter_id=chapter_id)
    return render_template(
        "glossary_scan.html",
        active_nav="glossary",
        result=result,
        chapter_filter=chapter_id,
    )


# --- JSON API ---------------------------------------------------------------

@bp.route("/api/list")
def api_list():
    category = request.args.get("category")
    entries = [svc.to_dict(e) for e in svc.list_entries(category=category)]
    return jsonify({"ok": True, "entries": entries})


@bp.route("/api/new", methods=["POST"])
def api_new():
    data = request.get_json(silent=True) or request.form
    try:
        e = svc.create_entry(
            term=(data.get("term") or "").strip(),
            category=data.get("category", "other"),
            definition=data.get("definition", ""),
            alternates=data.get("alternates") or None,
            forbidden=data.get("forbidden") or None,
            case_sensitive=bool(data.get("case_sensitive")),
            notes=data.get("notes", ""),
        )
        return jsonify({"ok": True, "id": e.id})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


@bp.route("/api/<entry_id>", methods=["POST"])
def api_update(entry_id: str):
    data = request.get_json(silent=True) or request.form
    try:
        svc.update_entry(entry_id, **data)
        return jsonify({"ok": True})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


@bp.route("/api/<entry_id>/delete", methods=["POST"])
def api_delete(entry_id: str):
    try:
        svc.delete_entry(entry_id)
        return jsonify({"ok": True})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


@bp.route("/api/scan")
def api_scan():
    chapter_id = request.args.get("chapter_id") or None
    result = svc.scan_chapters(chapter_id=chapter_id)
    return jsonify({"ok": True, **result})


@bp.route("/api/seed", methods=["POST"])
def api_seed():
    svc.seed_default_glossary()
    return jsonify({"ok": True})
