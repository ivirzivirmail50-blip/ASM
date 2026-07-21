"""Daily Writing Journal routes."""
from __future__ import annotations

import logging
from datetime import date, datetime

from flask import Blueprint, jsonify, render_template, request

from core.errors import AsmError
from services import journal_service as svc

log = logging.getLogger("asm.routes.journal")
bp = Blueprint("journal", __name__, url_prefix="/journal")


def _parse_date(s: str | None) -> date:
    if not s:
        return date.today()
    try:
        return date.fromisoformat(s)
    except ValueError:
        return date.today()


@bp.route("/")
def index():
    today_entry = svc.get_or_create_today()
    entries = [svc.to_dict(e) for e in svc.list_entries(limit=60)]
    stats = svc.stats(days=30)
    return render_template(
        "journal.html",
        active_nav="journal",
        today_entry=svc.to_dict(today_entry),
        entries=entries,
        stats=stats,
        moods=svc.JOURNAL_MOODS,
    )


# --- JSON API ---------------------------------------------------------------

@bp.route("/api/today")
def api_today():
    e = svc.get_or_create_today()
    return jsonify({"ok": True, "entry": svc.to_dict(e)})


@bp.route("/api/by-date/<date_str>")
def api_by_date(date_str: str):
    d = _parse_date(date_str)
    e = svc.get_by_date(d)
    if not e:
        return jsonify({"ok": True, "entry": None})
    return jsonify({"ok": True, "entry": svc.to_dict(e)})


@bp.route("/api/save", methods=["POST"])
def api_save():
    data = request.get_json(silent=True) or request.form
    entry_date = _parse_date(data.get("entry_date"))
    try:
        e = svc.create_or_update_for_date(
            entry_date,
            mood=data.get("mood"),
            energy=int(data["energy"]) if data.get("energy") else None,
            word_count_goal=int(data["word_count_goal"]) if data.get("word_count_goal") else None,
            word_count_actual=int(data["word_count_actual"]) if data.get("word_count_actual") else None,
            wins=data.get("wins"),
            struggles=data.get("struggles"),
            intentions=data.get("intentions"),
            gratitude=data.get("gratitude"),
            notes=data.get("notes"),
            tags=data.get("tags"),
        )
        return jsonify({"ok": True, "id": e.id})
    except (AsmError, ValueError) as exc:
        msg = getattr(exc, "user_message", str(exc))
        return jsonify({"ok": False, "error": msg}), getattr(exc, "status_code", 400)


@bp.route("/api/<entry_id>", methods=["POST"])
def api_update(entry_id: str):
    data = request.get_json(silent=True) or request.form
    fields = dict(data)
    if "energy" in fields and fields["energy"]:
        fields["energy"] = int(fields["energy"])
    if "word_count_goal" in fields and fields["word_count_goal"]:
        fields["word_count_goal"] = int(fields["word_count_goal"])
    if "word_count_actual" in fields and fields["word_count_actual"]:
        fields["word_count_actual"] = int(fields["word_count_actual"])
    try:
        svc.update_entry(entry_id, **fields)
        return jsonify({"ok": True})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


@bp.route("/api/<entry_id>/delete", methods=["POST"])
def api_delete(entry_id: str):
    try:
        svc.delete_entry(entry_id)
        return jsonify({"ok": True})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


@bp.route("/api/list")
def api_list():
    limit = request.args.get("limit", 60, type=int)
    entries = [svc.to_dict(e) for e in svc.list_entries(limit=limit)]
    return jsonify({"ok": True, "entries": entries})


@bp.route("/api/stats")
def api_stats():
    days = request.args.get("days", 30, type=int)
    return jsonify({"ok": True, **svc.stats(days=days)})
