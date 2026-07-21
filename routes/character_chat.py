"""Character AI Chat — talk to your characters as if they were real."""
from __future__ import annotations
from flask import Blueprint, render_template, jsonify, request, redirect, url_for
from services import character_service, ai_service, voice_service
from core.db import read_session
from models.settings import Setting

bp = Blueprint("character_chat", __name__, url_prefix="/character-chat")


def _ai_enabled():
    with read_session() as s:
        return Setting.get(s, "ai.enabled", "false") in (True, "true", "1", "on")


@bp.route("/")
def index():
    if not _ai_enabled():
        return redirect(url_for("settings.ai_settings"))
    characters = character_service.list_characters()
    return render_template("character_chat/index.html", active_nav="character_chat", characters=characters)


@bp.route("/api/chat", methods=["POST"])
def api_chat():
    data = request.get_json(silent=True) or request.form
    char_id = data.get("character_id")
    message = data.get("message", "")
    try:
        char = character_service.get_character(char_id)
        voice = voice_service.get_profile(char_id)
        voice_summary = voice_service.consistency_summary(char_id) if voice else ""
        prompt = f"""You are {char.name}, a {char.role} in a fantasy story.
Character background: {char.background or 'Unknown'}
Personality: {char.psychology or 'Complex'}
Voice: {voice_summary or 'Speak naturally'}

Stay in character as {char.name}. Respond to: "{message}"

Respond in 2-4 sentences, in character:"""
        result = ai_service.complete(prompt, max_tokens=200)
        return jsonify({"ok": True, "response": result, "character": char.name})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500
