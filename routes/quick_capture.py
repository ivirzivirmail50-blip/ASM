"""Quick Capture — fast capture from a single widget on the dashboard.

One unified endpoint that lets the writer quickly create:
- A note (via note_service)
- A chapter stub (via chapter_service)
- A journal entry update (via journal_service)
- A saved inspiration from a prompt (via inspiration_service)

The widget is a single text area with a type selector. Submits via AJAX
and shows a toast. No page reload.
"""
from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request

from core.errors import AsmError

log = logging.getLogger("asm.routes.quick_capture")
bp = Blueprint("quick_capture", __name__, url_prefix="/quick-capture")


@bp.route("/api/capture", methods=["POST"])
def api_capture():
    """Capture content as the specified type.

    Body: {type: note|chapter|journal, title?, body, category?, mood?}
    """
    data = request.get_json(silent=True) or request.form
    cap_type = data.get("type", "note")
    body = data.get("body", "").strip()
    title = (data.get("title") or "").strip()

    if not body and not title:
        return jsonify({"ok": False, "error": "Body or title required"}), 400

    try:
        if cap_type == "note":
            from services.note_service import create_note
            n = create_note(
                title=title or body[:80],
                body=body,
                category=data.get("category", "idea"),
            )
            return jsonify({"ok": True, "id": n.id, "type": "note",
                            "url": "/notes/"})

        elif cap_type == "chapter":
            from services.chapter_service import create_chapter
            ch = create_chapter(
                title=title or "Untitled Quick Capture",
                content=body,
                status="draft",
            )
            return jsonify({"ok": True, "id": ch.id, "type": "chapter",
                            "url": f"/chapters/{ch.id}"})

        elif cap_type == "journal":
            from datetime import date
            from services.journal_service import create_or_update_for_date
            e = create_or_update_for_date(
                date.today(),
                mood=data.get("mood", "ok"),
                notes=body,
            )
            return jsonify({"ok": True, "id": e.id, "type": "journal",
                            "url": "/journal/"})

        elif cap_type == "snippet":
            from services.snippet_service import create_snippet
            snip = create_snippet(
                name=title or body[:80],
                content=body,
                category="snippet",
            )
            return jsonify({"ok": True, "id": snip.id, "type": "snippet",
                            "url": "/snippets/"})

        else:
            return jsonify({"ok": False, "error": f"Unknown type: {cap_type}"}), 400

    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code
    except Exception as exc:
        log.exception("Quick capture failed")
        return jsonify({"ok": False, "error": str(exc)}), 500
