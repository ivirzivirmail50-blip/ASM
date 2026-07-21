"""Character Voice Profile routes."""
from __future__ import annotations

import logging

from flask import Blueprint, jsonify, render_template, request

from core.errors import AsmError
from services import character_service, voice_service as svc

log = logging.getLogger("asm.routes.voice")
bp = Blueprint("voice", __name__, url_prefix="/voice")


@bp.route("/")
def index():
    """List all characters with links to their voice profiles."""
    characters = character_service.list_characters()
    # Attach has_profile flag
    enriched = []
    for c in characters:
        v = svc.get_profile(c.id)
        enriched.append({
            "id": c.id,
            "name": c.name,
            "role": c.role,
            "avatar_color": c.avatar_color or "#6366f1",
            "has_profile": v is not None,
            "verbosity": v.speech_verbosity if v else None,
            "formality": v.formality if v else None,
        })
    return render_template(
        "voice_index.html",
        active_nav="voice",
        characters=enriched,
    )


@bp.route("/<character_id>")
def profile(character_id: str):
    """View/edit a character's voice profile."""
    try:
        c = character_service.get_character(character_id)
    except AsmError:
        from flask import abort
        abort(404)
    v = svc.get_or_create(character_id)
    profile_dict = svc.to_dict(v)
    return render_template(
        "voice_profile.html",
        active_nav="voice",
        character=c,
        profile=profile_dict,
        verbosity_levels=svc.VERBOSITY_LEVELS,
        formality_levels=svc.FORMALITY_LEVELS,
        sentence_lengths=svc.SENTENCE_LENGTHS,
    )


@bp.route("/<character_id>/scan")
def scan(character_id: str):
    """View dialogue consistency scan results for this character."""
    try:
        c = character_service.get_character(character_id)
    except AsmError:
        from flask import abort
        abort(404)
    result = svc.scan_dialogue(character_id)
    summary = svc.consistency_summary(character_id)
    return render_template(
        "voice_scan.html",
        active_nav="voice",
        character=c,
        result=result,
        summary=summary,
    )


# --- JSON API ---------------------------------------------------------------

@bp.route("/api/<character_id>", methods=["POST"])
def api_update(character_id: str):
    data = request.get_json(silent=True) or request.form
    # Parse comma-separated string fields into lists
    fields = dict(data)
    for k in ("favorite_words", "avoided_words", "catchphrases",
              "favorite_topics", "avoids_topics"):
        if k in fields and isinstance(fields[k], str):
            fields[k] = [s.strip() for s in fields[k].split("\n") if s.strip()]
    try:
        svc.update_profile(character_id, **fields)
        return jsonify({"ok": True})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


@bp.route("/api/<character_id>/scan")
def api_scan(character_id: str):
    try:
        result = svc.scan_dialogue(character_id)
        return jsonify({"ok": True, **result})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


@bp.route("/api/<character_id>/summary")
def api_summary(character_id: str):
    try:
        summary = svc.consistency_summary(character_id)
        return jsonify({"ok": True, "summary": summary})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code
