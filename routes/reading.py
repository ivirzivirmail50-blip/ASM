"""Reading Mode — continuous scroll across chapters, distraction-free.

Distinct from the chapter detail page (which is for editing). Reading Mode
is for the writer (or beta reader) to read the manuscript as a reader would:
- All (or scoped) chapters concatenated with chapter dividers
- Font family / size / line-height controls (persisted to settings)
- Theme: paper / sepia / dark / night
- Adjustable max-width
- Optional: hide chapter titles, hide synopsis, hide word counts
- Keyboard navigation: ← / → to jump between chapters, F for fullscreen
- Progress bar showing % of manuscript read
- Resume position (auto-saved via localStorage)
"""
from __future__ import annotations

import logging

from flask import Blueprint, jsonify, render_template, request

from services import chapter_service
from services._common import load_json

log = logging.getLogger("asm.routes.reading")
bp = Blueprint("reading", __name__, url_prefix="/reading")


@bp.route("/")
def index():
    """Reading mode entry — pick starting chapter and reading preferences."""
    chapters, total = chapter_service.list_chapters(per_page=10000)
    start_id = request.args.get("start") or (chapters[0].id if chapters else "")
    return render_template(
        "reading.html",
        active_nav="reading",
        chapters=chapters,
        start_id=start_id,
        total=total,
    )


@bp.route("/api/chapters")
def api_chapters():
    """Return all chapters' content for the reading mode renderer."""
    chapters, _ = chapter_service.list_chapters(per_page=10000)
    payload = []
    for ch in chapters:
        payload.append({
            "id": ch.id,
            "title": ch.title,
            "status": ch.status,
            "sort_order": ch.sort_order,
            "word_count": ch.word_count,
            "synopsis": ch.synopsis or "",
            "content": ch.content or "",
            "tags": load_json(ch.tags, []),
        })
    return jsonify({"ok": True, "chapters": payload, "total": len(payload)})
