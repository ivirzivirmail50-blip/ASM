"""Spell Check routes."""
from __future__ import annotations

import logging

from flask import Blueprint, jsonify, render_template, request

from core.errors import AsmError
from services import spellcheck_service as svc

log = logging.getLogger("asm.routes.spellcheck")
bp = Blueprint("spellcheck", __name__, url_prefix="/spellcheck")


@bp.route("/")
def index():
    """Spell check all chapters and show results."""
    result = svc.check_all_chapters()
    custom_words = [svc.to_dict(w) for w in svc.list_custom_words()]
    return render_template(
        "spellcheck.html",
        active_nav="spellcheck",
        result=result,
        custom_words=custom_words,
    )


@bp.route("/chapter/<chapter_id>")
def check_chapter(chapter_id: str):
    try:
        result = svc.check_chapter(chapter_id)
        return render_template(
            "spellcheck.html",
            active_nav="spellcheck",
            result={"chapters_checked": 1, "total_words": result["total_words"],
                    "total_flagged": result["flagged_count"], "results": [result]},
            custom_words=[svc.to_dict(w) for w in svc.list_custom_words()],
            single_chapter=True,
        )
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


# --- JSON API ---------------------------------------------------------------

@bp.route("/api/check")
def api_check_all():
    result = svc.check_all_chapters()
    return jsonify({"ok": True, **result})


@bp.route("/api/check/<chapter_id>")
def api_check_chapter(chapter_id: str):
    try:
        result = svc.check_chapter(chapter_id)
        return jsonify({"ok": True, **result})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


@bp.route("/api/words")
def api_list_words():
    words = [svc.to_dict(w) for w in svc.list_custom_words()]
    return jsonify({"ok": True, "words": words})


@bp.route("/api/words/add", methods=["POST"])
def api_add_word():
    data = request.get_json(silent=True) or request.form
    word = data.get("word", "")
    try:
        rec = svc.add_word(word)
        return jsonify({"ok": True, "id": rec.id, "word": rec.word})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


@bp.route("/api/words/add-batch", methods=["POST"])
def api_add_batch():
    data = request.get_json(silent=True) or request.form
    words = data.get("words") or []
    if isinstance(words, str):
        words = [w.strip() for w in words.split("\n") if w.strip()]
    count = svc.add_words_batch(words)
    return jsonify({"ok": True, "added": count})


@bp.route("/api/words/<word_id>/delete", methods=["POST"])
def api_delete_word(word_id: str):
    try:
        svc.remove_word(word_id)
        return jsonify({"ok": True})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


@bp.route("/api/words/by-text/<word>/delete", methods=["POST"])
def api_delete_word_by_text(word: str):
    svc.remove_word_by_text(word)
    return jsonify({"ok": True})
