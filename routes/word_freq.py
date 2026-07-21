"""Word Frequency Analyzer routes."""
from __future__ import annotations

import logging

from flask import Blueprint, jsonify, render_template, request

from services import word_freq_service as svc

log = logging.getLogger("asm.routes.word_freq")
bp = Blueprint("word_freq", __name__, url_prefix="/word-freq")


@bp.route("/")
def index():
    analysis = svc.analyze_manuscript(top_n=50)
    return render_template(
        "word_freq.html",
        active_nav="word_freq",
        analysis=analysis,
    )


@bp.route("/api/manuscript")
def api_manuscript():
    top_n = request.args.get("top_n", 50, type=int)
    return jsonify({"ok": True, **svc.analyze_manuscript(top_n=top_n)})


@bp.route("/api/chapter/<chapter_id>")
def api_chapter(chapter_id: str):
    top_n = request.args.get("top_n", 50, type=int)
    try:
        return jsonify({"ok": True, **svc.analyze_chapter(chapter_id, top_n=top_n)})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 404
