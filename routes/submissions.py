"""Submission Tracker routes."""
from __future__ import annotations

import logging
from datetime import date

from flask import Blueprint, jsonify, render_template, request

from core.errors import AsmError
from services import chapter_service, submission_service as svc

log = logging.getLogger("asm.routes.submissions")
bp = Blueprint("submissions", __name__, url_prefix="/submissions")


def _parse_date(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return date.fromisoformat(s)
    except ValueError:
        return None


@bp.route("/")
def index():
    status = request.args.get("status", "all")
    market_type = request.args.get("market_type", "all")
    subs = [svc.to_dict(s) for s in svc.list_submissions(
        status=status if status != "all" else None,
        market_type=market_type if market_type != "all" else None,
    )]
    stats = svc.stats()
    markets = svc.list_markets()
    return render_template(
        "submissions.html",
        active_nav="submissions",
        submissions=subs,
        stats=stats,
        markets=markets,
        statuses=svc.SUBMISSION_STATUSES,
        market_types=svc.MARKET_TYPES,
        current_status=status,
        current_market_type=market_type,
    )


# --- JSON API ---------------------------------------------------------------

@bp.route("/api/new", methods=["POST"])
def api_new():
    data = request.get_json(silent=True) or request.form
    try:
        sub = svc.create_submission(
            title=(data.get("title") or "").strip(),
            market_name=(data.get("market_name") or "").strip(),
            market_type=data.get("market_type", "magazine"),
            chapter_id=data.get("chapter_id") or None,
            status=data.get("status", "drafting"),
            submitted_date=_parse_date(data.get("submitted_date")),
            response_date=_parse_date(data.get("response_date")),
            response_type=data.get("response_type") or None,
            cover_letter=data.get("cover_letter", ""),
            notes=data.get("notes", ""),
        )
        return jsonify({"ok": True, "id": sub.id})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


@bp.route("/api/<sub_id>", methods=["POST"])
def api_update(sub_id: str):
    data = request.get_json(silent=True) or request.form
    fields = dict(data)
    if "submitted_date" in fields:
        fields["submitted_date"] = _parse_date(fields["submitted_date"])
    if "response_date" in fields:
        fields["response_date"] = _parse_date(fields["response_date"])
    try:
        svc.update_submission(sub_id, **fields)
        return jsonify({"ok": True})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


@bp.route("/api/<sub_id>/delete", methods=["POST"])
def api_delete(sub_id: str):
    try:
        svc.delete_submission(sub_id)
        return jsonify({"ok": True})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


@bp.route("/api/stats")
def api_stats():
    return jsonify({"ok": True, **svc.stats()})


@bp.route("/api/markets")
def api_markets():
    return jsonify({"ok": True, "markets": svc.list_markets()})


@bp.route("/api/chapters")
def api_chapters():
    """List chapters for the chapter-link dropdown."""
    chapters, _ = chapter_service.list_chapters(per_page=10000)
    return jsonify({"ok": True, "chapters": [
        {"id": c.id, "title": c.title, "status": c.status, "word_count": c.word_count}
        for c in chapters
    ]})
