"""AI Editor Copilot — AI-powered writing suggestions within the editor."""
from __future__ import annotations
from flask import Blueprint, render_template, jsonify, request, redirect, url_for
from services import ai_service, chapter_service
from core.db import read_session
from models.settings import Setting

bp = Blueprint("ai_copilot", __name__, url_prefix="/ai-copilot")


def _ai_enabled():
    with read_session() as s:
        return Setting.get(s, "ai.enabled", "false") in (True, "true", "1", "on")


@bp.route("/")
def index():
    if not _ai_enabled():
        return redirect(url_for("settings.ai_settings"))
    chapters, _ = chapter_service.list_chapters(per_page=10000)
    return render_template("ai_copilot/index.html", active_nav="ai_copilot", chapters=chapters)


@bp.route("/api/suggest", methods=["POST"])
def api_suggest():
    data = request.get_json(silent=True) or request.form
    text = data.get("text", "")
    action = data.get("action", "continue")
    try:
        if action == "continue":
            prompt = f"Continue this story naturally (2-3 sentences):\n\n{text[-500:]}"
        elif action == "shorter":
            prompt = f"Rewrite this passage to be more concise:\n\n{text}"
        elif action == "expand":
            prompt = f"Expand this passage with more sensory details:\n\n{text}"
        elif action == "dialogue":
            prompt = f"Write a natural dialogue response for the character in this scene:\n\n{text[-500:]}"
        else:
            prompt = text

        result = ai_service.complete(prompt, max_tokens=200)
        return jsonify({"ok": True, "suggestion": result})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500
