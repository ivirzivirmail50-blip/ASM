"""Snippets & chapter templates routes."""
from __future__ import annotations

import logging

from flask import Blueprint, jsonify, render_template, request

from core.errors import AsmError
from services import snippet_service

log = logging.getLogger("asm.routes.snippets")
bp = Blueprint("snippets", __name__, url_prefix="/snippets")


@bp.route("/")
def index():
    snippets = snippet_service.list_snippets()
    # Group by category
    templates = [s for s in snippets if s.category == "template"]
    user_snippets = [s for s in snippets if s.category == "snippet"]
    return render_template("snippets.html", templates=templates,
                           snippets=user_snippets, active_nav="snippets")


@bp.route("/new", methods=["POST"])
def create():
    data = request.get_json(silent=True) or request.form
    try:
        snip = snippet_service.create_snippet(
            name=data.get("name", "").strip(),
            content=data.get("content", ""),
            category=data.get("category", "snippet"),
        )
        return jsonify({"ok": True, "id": snip.id, "name": snip.name})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


@bp.route("/<snippet_id>", methods=["POST"])
def update(snippet_id: str):
    data = request.get_json(silent=True) or request.form
    try:
        snippet_service.update_snippet(snippet_id, **data)
        return jsonify({"ok": True})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


@bp.route("/<snippet_id>/delete", methods=["POST"])
def delete(snippet_id: str):
    try:
        snippet_service.delete_snippet(snippet_id)
        return jsonify({"ok": True})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


@bp.route("/<snippet_id>/content")
def get_content(snippet_id: str):
    """Return snippet content as plain text (for editor insertion)."""
    try:
        snip = snippet_service.get_snippet(snippet_id)
        from flask import Response
        return Response(snip.content or "", mimetype="text/plain")
    except AsmError:
        from flask import abort
        abort(404)


@bp.route("/seed-templates", methods=["POST"])
def seed_templates():
    """Seed default chapter templates."""
    snippet_service.seed_default_templates()
    return jsonify({"ok": True})
