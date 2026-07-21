"""Web Serial Platform — publish chapters as a serial with reader view."""
from __future__ import annotations
from flask import Blueprint, render_template, jsonify, request
from services import chapter_service

bp = Blueprint("serial_platform", __name__, url_prefix="/serial")


@bp.route("/")
def index():
    chapters, total = chapter_service.list_chapters(per_page=10000)
    return render_template("serial_platform/index.html", active_nav="serial",
                           chapters=chapters, total=total)


@bp.route("/read/<chapter_id>")
def read(chapter_id: str):
    try:
        ch = chapter_service.get_chapter(chapter_id)
        prev_n, next_n = chapter_service.get_neighbors(chapter_id)
        return render_template("serial_platform/read.html", chapter=ch,
                               prev_ch=prev_n, next_ch=next_n)
    except Exception:
        from flask import abort
        abort(404)
