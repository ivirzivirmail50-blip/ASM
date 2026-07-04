"""AI History route — view past AI-generated outputs."""
from __future__ import annotations

import logging

from flask import Blueprint, jsonify, render_template, request

from services import ai_history_service

log = logging.getLogger("asm.routes.ai_history")
bp = Blueprint("ai_history", __name__)


@bp.route("/ai-history")
def index():
    """View AI action history."""
    action_filter = request.args.get("type", "")
    entries = ai_history_service.list_recent(limit=100,
                                             action_type=action_filter or None)
    return render_template("ai_history.html", entries=entries,
                           action_filter=action_filter,
                           active_nav="ai_history")


@bp.route("/ai-history/<int:entry_id>/delete", methods=["POST"])
def delete(entry_id: int):
    ai_history_service.delete(entry_id)
    return jsonify({"ok": True})


@bp.route("/ai-history/clear", methods=["POST"])
def clear_all():
    ai_history_service.clear_all()
    return jsonify({"ok": True})
