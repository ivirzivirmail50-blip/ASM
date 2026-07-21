"""Research & References routes."""
from __future__ import annotations

import logging

from flask import Blueprint, jsonify, render_template, request

from core.errors import AsmError
from services import reference_service as svc

log = logging.getLogger("asm.routes.references")
bp = Blueprint("references", __name__, url_prefix="/references")


@bp.route("/")
def index():
    source_type = request.args.get("source_type", "all")
    read_status = request.args.get("read_status", "all")
    priority = request.args.get("priority", "all")
    tag = request.args.get("tag", "")
    search = request.args.get("q", "")
    refs = [svc.to_dict(r) for r in svc.list_references(
        source_type=source_type if source_type != "all" else None,
        read_status=read_status if read_status != "all" else None,
        priority=priority if priority != "all" else None,
        tag=tag or None,
        search=search or None,
    )]
    stats = svc.stats()
    all_tags = svc.all_tags()
    return render_template(
        "references.html",
        active_nav="references",
        references=refs,
        stats=stats,
        all_tags=all_tags,
        source_types=svc.REFERENCE_TYPES,
        read_statuses=svc.READ_STATUSES,
        priorities=svc.PRIORITIES,
        current_source_type=source_type,
        current_read_status=read_status,
        current_priority=priority,
        current_tag=tag,
        current_search=search,
    )


# --- JSON API ---------------------------------------------------------------

@bp.route("/api/new", methods=["POST"])
def api_new():
    data = request.get_json(silent=True) or request.form
    try:
        r = svc.create_reference(
            title=(data.get("title") or "").strip(),
            author=data.get("author", ""),
            url=data.get("url", ""),
            source_type=data.get("source_type", "article"),
            publication_date=data.get("publication_date", ""),
            publisher=data.get("publisher", ""),
            isbn_or_doi=data.get("isbn_or_doi", ""),
            description=data.get("description", ""),
            quotes=data.get("quotes") or None,
            tags=data.get("tags") or None,
            chapter_ids=data.get("chapter_ids") or None,
            read_status=data.get("read_status", "unread"),
            priority=data.get("priority", "medium"),
            rating=int(data["rating"]) if data.get("rating") else None,
            notes=data.get("notes", ""),
        )
        return jsonify({"ok": True, "id": r.id})
    except (AsmError, ValueError) as exc:
        msg = getattr(exc, "user_message", str(exc))
        return jsonify({"ok": False, "error": msg}), getattr(exc, "status_code", 400)


@bp.route("/api/<ref_id>", methods=["POST"])
def api_update(ref_id: str):
    data = request.get_json(silent=True) or request.form
    try:
        svc.update_reference(ref_id, **data)
        return jsonify({"ok": True})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


@bp.route("/api/<ref_id>/delete", methods=["POST"])
def api_delete(ref_id: str):
    try:
        svc.delete_reference(ref_id)
        return jsonify({"ok": True})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


@bp.route("/api/stats")
def api_stats():
    return jsonify({"ok": True, **svc.stats()})
