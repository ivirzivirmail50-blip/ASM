"""Manuscript Compile Wizard routes."""
from __future__ import annotations

import logging

from flask import Blueprint, jsonify, render_template, request, send_file

from core.errors import AsmError
from services import compile_service as svc

log = logging.getLogger("asm.routes.compile")
bp = Blueprint("compile", __name__, url_prefix="/compile")


@bp.route("/")
def index():
    config = svc.get_config()
    return render_template(
        "compile.html",
        active_nav="compile",
        config=config,
    )


@bp.route("/api/config", methods=["GET", "POST"])
def api_config():
    if request.method == "GET":
        return jsonify({"ok": True, "config": svc.get_config()})
    data = request.get_json(silent=True) or request.form
    try:
        saved = svc.save_config(dict(data))
        return jsonify({"ok": True, "config": saved})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


@bp.route("/api/preview")
def api_preview():
    """Compile and return the structure (sections list) for preview."""
    config = svc.get_config()
    compiled = svc.compile_manuscript(config)
    # Don't return the full body of chapters (could be huge); just metadata
    preview_sections = []
    for sec in compiled["sections"]:
        preview_sections.append({
            "type": sec["type"],
            "heading": sec["heading"],
            "body_preview": (sec["body"] or "")[:500] + ("…" if len(sec.get("body") or "") > 500 else ""),
            "word_count": sec.get("word_count"),
        })
    return jsonify({
        "ok": True,
        "title": compiled["title"],
        "author": compiled["author"],
        "sections": preview_sections,
        "total_words": compiled["total_words"],
        "chapter_count": compiled["chapter_count"],
    })


@bp.route("/download")
def download():
    """Compile and download the manuscript."""
    fmt = request.args.get("format", "html")
    config = svc.get_config()
    config["format"] = fmt
    try:
        compiled = svc.compile_manuscript(config)
        content, mime, filename = svc.render_compiled(compiled, fmt)
        import io
        return send_file(
            io.BytesIO(content),
            mimetype=mime,
            as_attachment=True,
            download_name=filename,
        )
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code
