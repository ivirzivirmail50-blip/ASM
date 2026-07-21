"""Beta reader routes — read-only chapter viewing + threaded comments."""
from __future__ import annotations

import logging

from flask import Blueprint, abort, jsonify, render_template, request

from core.errors import AsmError, NotFoundError
from services import beta_service, chapter_service

log = logging.getLogger("asm.routes.beta")
bp = Blueprint("beta", __name__)


@bp.route("/beta/<chapter_id>")
def reader(chapter_id: str):
    """Beta reader view: read-only chapter + comment sidebar."""
    try:
        ch = chapter_service.get_chapter(chapter_id)
        comments = beta_service.get_threaded(chapter_id)
        stats = beta_service.stats(chapter_id)
        return render_template("beta_reader.html", chapter=ch,
                               comments=comments, stats=stats,
                               active_nav="chapters")
    except NotFoundError:
        abort(404)


@bp.route("/beta/<chapter_id>/comment", methods=["POST"])
def add_comment(chapter_id: str):
    """Add a beta reader comment (top-level)."""
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


@bp.route("/beta/comment/<int:comment_id>/reply", methods=["POST"])
def add_reply(comment_id: int):
    """Add a reply to an existing comment."""
    data = request.get_json(silent=True) or request.form
    comment = (data.get("comment") or "").strip()
    if not comment:
        return jsonify({"ok": False, "error": "Reply text required"}), 400
    try:
        reply = beta_service.add_reply(
            comment_id, comment,
            reader_name=data.get("reader_name", "Author"),
            is_author_reply=bool(data.get("is_author_reply", True)),
        )
        return jsonify({"ok": True, "id": reply.id, "comment": reply.comment,
                        "reader": reply.reader_name})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


@bp.route("/beta/comment/<int:comment_id>/resolve", methods=["POST"])
def resolve_comment(comment_id: int):
    try:
        c = beta_service.resolve_comment(comment_id)
        return jsonify({"ok": True, "status": c.status})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


@bp.route("/beta/comment/<int:comment_id>/reopen", methods=["POST"])
def reopen_comment(comment_id: int):
    try:
        c = beta_service.reopen_comment(comment_id)
        return jsonify({"ok": True, "status": c.status})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


@bp.route("/beta/comment/<int:comment_id>/delete", methods=["POST"])
def delete_comment(comment_id: int):
    beta_service.delete_comment(comment_id)
    return jsonify({"ok": True})


@bp.route("/beta/<chapter_id>/threaded")
def api_threaded(chapter_id: str):
    """Return comments as threaded JSON structure."""
    return jsonify({"ok": True, "comments": beta_service.get_threaded(chapter_id),
                    "stats": beta_service.stats(chapter_id)})


@bp.route("/beta/<chapter_id>/stats")
def api_stats(chapter_id: str):
    return jsonify({"ok": True, **beta_service.stats(chapter_id)})
