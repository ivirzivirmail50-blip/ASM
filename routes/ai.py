"""AI routes — invisible (404) when AI disabled."""
from __future__ import annotations

import logging

from flask import (Blueprint, jsonify, request)

from core.errors import AiDisabledError, AsmError
from services import ai_service
from services import ai_history_service

log = logging.getLogger("asm.routes.ai")
bp = Blueprint("ai", __name__, url_prefix="/ai")


def _guard():
    """Return an error response if AI is disabled."""
    if not ai_service.is_enabled():
        from flask import abort
        abort(404)


@bp.route("/status")
def status():
    if not ai_service.is_enabled():
        return jsonify({"enabled": False})
    return jsonify({"enabled": True})


@bp.route("/continue", methods=["POST"])
def continue_writing():
    _guard()
    data = request.get_json(silent=True) or {}
    text = data.get("text", "")
    try:
        out = ai_service.continue_writing(text,
                                          max_tokens=int(data.get("max_tokens", 400)))
        ai_history_service.save("continue", out,
                                prompt_summary="Basic continuation")
        return jsonify({"ok": True, "response": out})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


@bp.route("/continue-context", methods=["POST"])
def continue_with_context():
    """Context-aware AI continuation: sends character/world + recent summaries."""
    _guard()
    data = request.get_json(silent=True) or {}
    text = data.get("text", "")
    chapter_id = data.get("chapter_id")
    tone = data.get("tone", "")
    try:
        # Gather context
        from services import chapter_service, character_service, world_service
        from services._common import load_json

        # Characters linked to this chapter
        char_profiles = []
        if chapter_id:
            ch = chapter_service.get_chapter(chapter_id)
            linked_ids = load_json(ch.character_ids, [])
            for cid in linked_ids:
                try:
                    c = character_service.get_character(cid)
                    char_profiles.append({
                        "name": c.name, "physical": c.physical,
                        "psychology": c.psychology, "voice": c.voice,
                    })
                except Exception:
                    pass

        # If no linked characters, send top 5 by name
        if not char_profiles:
            all_chars = character_service.list_characters()[:5]
            char_profiles = [{"name": c.name, "physical": c.physical,
                              "psychology": c.psychology, "voice": c.voice}
                             for c in all_chars]

        # World entries (top 5)
        world_entries = []
        try:
            entries = world_service.list_entries(per_page=5)[0]
            world_entries = [{"name": e.name, "type": e.type, "description": e.description}
                             for e in entries]
        except Exception:
            pass

        # Recent chapter synopses (last 3)
        recent_summaries = []
        all_chapters = chapter_service.list_chapters(sort="sort_order")[0]
        if chapter_id:
            # Find chapters before this one
            ch_idx = next((i for i, c in enumerate(all_chapters) if c.id == chapter_id), 0)
            for c in all_chapters[max(0, ch_idx-3):ch_idx]:
                recent_summaries.append(c.synopsis or c.title)
        else:
            for c in all_chapters[-3:]:
                recent_summaries.append(c.synopsis or c.title)

        out = ai_service.continue_with_context(
            text,
            character_profiles=char_profiles,
            world_entries=world_entries,
            recent_summaries=recent_summaries,
            tone=tone,
            max_tokens=int(data.get("max_tokens", 500)),
            entity_id=chapter_id,
        )
        ai_history_service.save("continue_context", out,
                                entity_type="chapter", entity_id=chapter_id or "",
                                prompt_summary="Context-aware continuation",
                                metadata={"characters": len(char_profiles),
                                          "world": len(world_entries),
                                          "summaries": len(recent_summaries)})
        return jsonify({"ok": True, "response": out,
                        "context": {"characters": len(char_profiles),
                                    "world": len(world_entries),
                                    "summaries": len(recent_summaries)}})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


@bp.route("/summarize", methods=["POST"])
def summarize():
    _guard()
    data = request.get_json(silent=True) or {}
    try:
        out = ai_service.summarize(data.get("text", ""))
        return jsonify({"ok": True, "response": out})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


@bp.route("/rewrite", methods=["POST"])
def rewrite():
    _guard()
    data = request.get_json(silent=True) or {}
    try:
        out = ai_service.rewrite(data.get("text", ""), data.get("tone", "neutral"))
        return jsonify({"ok": True, "response": out})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


@bp.route("/suggest-tags", methods=["POST"])
def suggest_tags():
    _guard()
    data = request.get_json(silent=True) or {}
    try:
        out = ai_service.suggest_tags(data.get("text", ""))
        return jsonify({"ok": True, "tags": out})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


@bp.route("/suggest-synopsis", methods=["POST"])
def suggest_synopsis():
    _guard()
    data = request.get_json(silent=True) or {}
    try:
        out = ai_service.suggest_synopsis(data.get("text", ""))
        return jsonify({"ok": True, "synopsis": out})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


@bp.route("/generate-name", methods=["POST"])
def generate_name():
    _guard()
    data = request.get_json(silent=True) or {}
    try:
        culture = data.get("culture", "fantasy")
        kind = data.get("kind", "character")
        out = ai_service.generate_name(culture=culture, kind=kind)
        ai_history_service.save("name_gen", "\n".join(out),
                                prompt_summary=f"{culture} {kind} names",
                                metadata={"culture": culture, "kind": kind})
        return jsonify({"ok": True, "names": out})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


@bp.route("/generate-dialogue", methods=["POST"])
def generate_dialogue():
    """Generate dialogue in a character's voice."""
    _guard()
    data = request.get_json(silent=True) or {}
    character_id = data.get("character_id")
    try:
        # Fetch character profile
        from services import character_service
        ch = character_service.get_character(character_id)
        out = ai_service.generate_dialogue(
            character_name=ch.name,
            character_voice=ch.voice or "",
            character_psychology=ch.psychology or "",
            other_character=data.get("other_character", ""),
            scene_context=data.get("scene_context", ""),
            emotion=data.get("emotion", "neutral"),
            entity_id=character_id,
        )
        ai_history_service.save("dialogue", out,
                                entity_type="character", entity_id=character_id,
                                entity_title=ch.name,
                                prompt_summary=f"Dialogue for {ch.name} ({data.get('emotion', 'neutral')})",
                                metadata={"emotion": data.get("emotion", "neutral"),
                                          "other": data.get("other_character", "")})
        return jsonify({"ok": True, "dialogue": out,
                        "character": ch.name})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


@bp.route("/consistency-check", methods=["POST"])
def consistency_check():
    """Run a consistency check across chapters vs character/world DB."""
    _guard()
    try:
        from services import chapter_service, character_service, world_service
        from services._common import load_json
        chapters = chapter_service.list_chapters(sort="sort_order")[0]
        chapter_texts = [{"title": c.title, "content": c.content}
                         for c in chapters[:10]]
        characters = character_service.list_characters()
        char_profiles = [{"name": c.name, "physical": c.physical,
                          "psychology": c.psychology, "background": c.background}
                         for c in characters]
        world = world_service.list_entries()[0]  # list_entries now returns (entries, total)
        world_entries = [{"name": w.name, "type": w.type,
                          "description": w.description, "content": w.content}
                         for w in world]
        findings = ai_service.consistency_check(
            chapter_texts, char_profiles, world_entries,
        )
        import json as _json
        ai_history_service.save("consistency", _json.dumps(findings, indent=2),
                                prompt_summary=f"Consistency check ({len(findings)} findings)")
        return jsonify({"ok": True, "findings": findings,
                        "count": len(findings)})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


@bp.route("/continue-stream", methods=["POST"])
def continue_stream():
    """Streaming version of /ai/continue — yields text chunks via SSE."""
    _guard()
    data = request.get_json(silent=True) or {}
    text = data.get("text", "")
    from flask import Response, stream_with_context

    def generate():
        try:
            prompt = (
                "Continue the following story text in the same style and tone. "
                "Return only the continuation, no preamble.\n\n"
                f"...{text[-1000:]}"
            )
            for chunk, is_final in ai_service.generate_streaming(
                prompt, max_tokens=int(data.get("max_tokens", 400)),
                temperature=0.8,
            ):
                if chunk:
                    yield f"data: {chunk}\n\n"
                if is_final:
                    yield "data: [DONE]\n\n"
                    return
        except AsmError as exc:
            yield f"data: [ERROR] {exc.user_message}\n\n"
        except Exception as exc:
            yield f"data: [ERROR] {exc}\n\n"

    return Response(stream_with_context(generate()),
                    mimetype="text/event-stream")
