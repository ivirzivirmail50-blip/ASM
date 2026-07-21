"""Writing Analytics routes."""
from __future__ import annotations

import logging

from flask import Blueprint, jsonify, render_template

from services import analytics_service as svc

log = logging.getLogger("asm.routes.analytics")
bp = Blueprint("analytics", __name__, url_prefix="/analytics")


@bp.route("/")
def index():
    chapters = svc.all_chapters_analytics()
    summary = svc.manuscript_summary()
    top_words = svc.top_words(limit=30)
    char_screen = svc.character_screen_time()
    return render_template(
        "analytics.html",
        active_nav="analytics",
        chapters=chapters,
        summary=summary,
        top_words=top_words,
        char_screen=char_screen,
    )


@bp.route("/api/chapters")
def api_chapters():
    return jsonify({"ok": True, "chapters": svc.all_chapters_analytics()})


@bp.route("/api/summary")
def api_summary():
    return jsonify({"ok": True, **svc.manuscript_summary()})


@bp.route("/api/top-words")
def api_top_words():
    limit = 30
    return jsonify({"ok": True, "words": svc.top_words(limit=limit)})
