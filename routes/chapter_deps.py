"""Chapter Dependency Tracker routes."""
from __future__ import annotations

import logging

from flask import Blueprint, jsonify, render_template, request

from core.errors import AsmError
from services import chapter_deps_service as svc, chapter_service

log = logging.getLogger("asm.routes.chapter_deps")
bp = Blueprint("chapter_deps", __name__, url_prefix="/chapter-deps")


@bp.route("/")
def index():
    graph = svc.get_dependency_graph()
    chapters, _ = chapter_service.list_chapters(per_page=10000)
    return render_template(
        "chapter_deps.html",
        active_nav="chapter_deps",
        graph=graph,
        chapters=chapters,
    )


@bp.route("/api/graph")
def api_graph():
    return jsonify({"ok": True, **svc.get_dependency_graph()})


@bp.route("/api/add", methods=["POST"])
def api_add():
    data = request.get_json(silent=True) or request.form
    try:
        dep = svc.add_dependency(
            data.get("from_chapter_id", ""),
            data.get("to_chapter_id", ""),
        )
        return jsonify({"ok": True, "id": dep.id})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


@bp.route("/api/remove", methods=["POST"])
def api_remove():
    data = request.get_json(silent=True) or request.form
    try:
        svc.remove_dependency(
            data.get("from_chapter_id", ""),
            data.get("to_chapter_id", ""),
        )
        return jsonify({"ok": True})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code
