"""Story Bible Auto-Generator routes."""
from __future__ import annotations

import logging

from flask import Blueprint, jsonify, render_template, request, send_file

from services import story_bible_service as svc

log = logging.getLogger("asm.routes.story_bible")
bp = Blueprint("story_bible", __name__, url_prefix="/story-bible")


@bp.route("/")
def index():
    """Preview the story bible structure."""
    data = svc.gather_data()
    return render_template(
        "story_bible.html",
        active_nav="story_bible",
        data=data,
    )


@bp.route("/api/data")
def api_data():
    data = svc.gather_data()
    return jsonify({"ok": True, "data": data})


@bp.route("/download")
def download():
    fmt = request.args.get("format", "html")
    data = svc.gather_data()
    try:
        content, mime, filename = svc.render(data, fmt)
        import io
        return send_file(
            io.BytesIO(content),
            mimetype=mime,
            as_attachment=True,
            download_name=filename,
        )
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
