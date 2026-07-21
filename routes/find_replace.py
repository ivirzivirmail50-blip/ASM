"""Bulk Find & Replace routes."""
from __future__ import annotations

import logging

from flask import Blueprint, jsonify, render_template, request

from core.errors import AsmError
from services import chapter_service, find_replace_service as svc

log = logging.getLogger("asm.routes.find_replace")
bp = Blueprint("find_replace", __name__, url_prefix="/find-replace")


@bp.route("/")
def index():
    chapters, _ = chapter_service.list_chapters(per_page=10000)
    return render_template(
        "find_replace.html",
        active_nav="find_replace",
        chapters=chapters,
    )


@bp.route("/api/preview", methods=["POST"])
def api_preview():
    data = request.get_json(silent=True) or request.form
    try:
        result = svc.preview(
            pattern=data.get("pattern", ""),
            replacement=data.get("replacement", ""),
            use_regex=bool(data.get("use_regex")),
            case_sensitive=bool(data.get("case_sensitive")),
            whole_word=bool(data.get("whole_word")),
            scope_chapter_ids=data.get("scope_chapter_ids") or None,
            scope_status=data.get("scope_status") or None,
        )
        return jsonify({"ok": True, **result})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


@bp.route("/api/apply", methods=["POST"])
def api_apply():
    data = request.get_json(silent=True) or request.form
    try:
        result = svc.apply(
            pattern=data.get("pattern", ""),
            replacement=data.get("replacement", ""),
            use_regex=bool(data.get("use_regex")),
            case_sensitive=bool(data.get("case_sensitive")),
            whole_word=bool(data.get("whole_word")),
            scope_chapter_ids=data.get("scope_chapter_ids") or None,
            scope_status=data.get("scope_status") or None,
        )
        return jsonify({"ok": True, **result})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code
