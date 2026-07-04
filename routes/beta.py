"""Beta reader routes — read-only chapter viewing + comments."""
from __future__ import annotations

import logging

from flask import Blueprint, abort, jsonify, render_template, request

from core.errors import NotFoundError
from services import beta_service, chapter_service

log = logging.getLogger("asm.routes.beta")
bp = Blueprint("beta", __name__)


@bp.route("/beta/<chapter_id>")
def reader(chapter_id: str):
    """Beta reader view: read-only chapter + comment sidebar."""
    try:
        ch = chapter_service.get_chapter(chapter_id)
        comments = beta_service.list_comments(chapter_id)
        open_count = beta_service.count_open(chapter_id)
        return render_template("beta_reader.html", chapter=ch,
                               comments=comments, open_count=open_count,
                               active_nav="chapters")
    except NotFoundError:
        abort(404)


@bp.route("/beta/<chapter_id>/comment", methods=["POST"])
def add_comment(chapter_id: str):
    """Add a beta reader comment."""
    data = request.get_json(silent=True) or request.form
    comment = (data.get("comment") or "").strip()
    if not comment:
        return jsonify({"ok": False, "error": "Comment required"}), 400
    try:
        c = beta_service.add_comment(
            chapter_id, comment,
            reader_name=data.get("reader_name", "Beta Reader"),
            selected_text=data.get("selected_text", ""),
            position=int(data.get("position", 0)),
        )
        return jsonify({"ok": True, "id": c.id, "reader": c.reader_name,
                        "comment": c.comment, "status": c.status})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@bp.route("/beta/comment/<int:comment_id>/resolve", methods=["POST"])
def resolve_comment(comment_id: int):
    beta_service.resolve_comment(comment_id)
    return jsonify({"ok": True})


@bp.route("/beta/comment/<int:comment_id>/delete", methods=["POST"])
def delete_comment(comment_id: int):
    beta_service.delete_comment(comment_id)
    return jsonify({"ok": True})
