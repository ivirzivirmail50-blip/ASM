"""Plan routes — Kanban, outline, timeline, subtasks."""
from __future__ import annotations

import json
import logging
from datetime import date

from flask import (Blueprint, abort, jsonify, render_template, request,
                   url_for)

from core.errors import AsmError, NotFoundError
from services import plan_service
from services._common import load_json

log = logging.getLogger("asm.routes.plans")
bp = Blueprint("plans", __name__, url_prefix="/plans")


@bp.route("/")
def board():
    plans = plan_service.list_plans()
    plan_ids = [p.id for p in plans]
    # Compute subtask counts, actual word counts, dependency warnings, overdue
    subtask_counts = plan_service.subtask_counts_for_plans(plan_ids)
    actual_words = plan_service.actual_word_counts_for_plans(plan_ids)
    dep_warnings = plan_service.dependency_warnings(plan_ids)
    overdue_ids = set(plan_service.overdue_plans())
    by_col: dict[str, list] = {c: [] for c in plan_service.STATUS_COLUMNS}
    for p in plans:
        by_col.setdefault(p.column or p.status, []).append(p)
    # Sort each column by sort_order
    for col in by_col:
        by_col[col].sort(key=lambda x: x.sort_order or 0)
    return render_template("plans/board.html", columns=by_col,
                           statuses=plan_service.STATUS_COLUMNS,
                           subtask_counts=subtask_counts,
                           actual_words=actual_words,
                           dep_warnings=dep_warnings,
                           overdue_ids=overdue_ids,
                           all_plans=plans,
                           active_nav="plans")


@bp.route("/new", methods=["GET", "POST"])
def new():
    if request.method == "POST":
        data = request.form
        try:
            deadline = None
            if data.get("deadline"):
                deadline = date.fromisoformat(data["deadline"])
            p = plan_service.create_plan(
                title=data.get("title", "").strip(),
                description=data.get("description") or None,
                status=data.get("status", "idea"),
                track=data.get("track") or None,
                story_date=data.get("story_date") or None,
                event_type=data.get("event_type") or None,
                deadline=deadline,
                effort_estimate=int(data.get("effort_estimate") or 0) or None,
                characters_involved=request.form.getlist("characters_involved"),
                tags=[t.strip() for t in data.get("tags", "").split(",") if t.strip()],
            )
            return jsonify({"ok": True, "id": p.id,
                            "url": url_for("plans.detail", plan_id=p.id)})
        except AsmError as exc:
            return jsonify({"ok": False, "error": exc.user_message}), exc.status_code
    from services import character_service
    chars = character_service.list_characters()
    return render_template("plans/new.html", characters=chars,
                           statuses=plan_service.STATUS_COLUMNS,
                           active_nav="plans")


@bp.route("/<plan_id>")
def detail(plan_id: str):
    try:
        p = plan_service.get_plan(plan_id)
        subtasks = plan_service.list_subtasks(plan_id)
        from services import character_service, chapter_service
        chars = character_service.list_characters()
        chapters = chapter_service.list_chapters(sort="sort_order")[0]
        linked_chars = []
        for cid in load_json(p.characters_involved, []):
            try:
                linked_chars.append(character_service.get_character(cid))
            except NotFoundError:
                pass
        return render_template("plans/detail.html", plan=p, subtasks=subtasks,
                               characters=chars, chapters=chapters,
                               linked_chars=linked_chars,
                               tags=load_json(p.tags, []),
                               statuses=plan_service.STATUS_COLUMNS,
                               active_nav="plans")
    except NotFoundError:
        abort(404)


@bp.route("/<plan_id>/edit", methods=["GET", "POST"])
def edit(plan_id: str):
    try:
        p = plan_service.get_plan(plan_id)
    except NotFoundError:
        abort(404)
    if request.method == "POST":
        data = request.form
        try:
            deadline = None
            if data.get("deadline"):
                deadline = date.fromisoformat(data["deadline"])
            plan_service.update_plan(plan_id,
                title=data.get("title", "").strip(),
                description=data.get("description") or None,
                status=data.get("status") or None,
                track=data.get("track") or None,
                story_date=data.get("story_date") or None,
                event_type=data.get("event_type") or None,
                deadline=deadline,
                effort_estimate=int(data.get("effort_estimate") or 0) or None,
                chapter_id=data.get("chapter_id") or None,
                characters_involved=request.form.getlist("characters_involved"),
                tags=[t.strip() for t in data.get("tags", "").split(",") if t.strip()],
            )
            return jsonify({"ok": True, "url": url_for("plans.detail", plan_id=plan_id)})
        except AsmError as exc:
            return jsonify({"ok": False, "error": exc.user_message}), exc.status_code
    from services import character_service, chapter_service
    chars = character_service.list_characters()
    chapters = chapter_service.list_chapters(sort="sort_order")[0]
    all_plans = plan_service.list_plans()
    return render_template("plans/edit.html", plan=p,
                           characters=chars, chapters=chapters,
                           all_plans=all_plans,
                           linked_char_ids=load_json(p.characters_involved, []),
                           tags=load_json(p.tags, []),
                           active_nav="plans")


@bp.route("/<plan_id>/delete", methods=["POST"])
def delete(plan_id: str):
    try:
        label = plan_service.delete_plan(plan_id)
        return jsonify({"ok": True, "url": url_for("plans.board"),
                        "label": label, "undoable": True})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


@bp.route("/<plan_id>/status", methods=["POST"])
def change_status(plan_id: str):
    data = request.get_json(silent=True) or {}
    new_status = data.get("status", "")
    try:
        plan_service.change_status(plan_id, new_status)
        return jsonify({"ok": True})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


@bp.route("/reorder", methods=["POST"])
def reorder():
    """Reorder plans across columns. Payload: {column: [ids]}."""
    data = request.get_json(silent=True) or {}
    try:
        plan_service.reorder_all(data)
        return jsonify({"ok": True})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


@bp.route("/reorder-nested", methods=["POST"])
def reorder_nested():
    """Reorder outline items with parent_id changes.

    Payload: {items: [{id, parent_id, sort_order}, ...]}
    """
    data = request.get_json(silent=True) or {}
    items = data.get("items", [])
    try:
        plan_service.reorder_nested(items)
        return jsonify({"ok": True})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


@bp.route("/outline")
def outline():
    plans = plan_service.list_plans()
    # Build nested tree
    by_id = {p.id: p for p in plans}
    roots = []
    for p in plans:
        if p.parent_id and p.parent_id in by_id:
            continue
        roots.append(p)
    return render_template("plans/outline.html", plans=plans, roots=roots,
                           by_id=by_id, active_nav="plans_outline")


@bp.route("/timeline")
def timeline():
    plans = plan_service.list_plans()
    # Get saved track order
    track_order = plan_service.get_track_order()
    # Group by track, sorted by story_date within each track
    tracks: dict[str, list] = {}
    for p in plans:
        track = p.track or "Main Plot"
        tracks.setdefault(track, []).append(p)
    # Sort events within each track by story_date (chronological, natural sort)
    import re as _re
    def _sort_key(p):
        """Natural sort key for story_date: extracts numbers for proper ordering."""
        d = p.story_date or ""
        # Extract all numbers from the date string for natural sorting
        # e.g., "Day 10" -> [10], "Day 3" -> [3], "Year 321, Month 5" -> [321, 5]
        nums = [int(n) for n in _re.findall(r'\d+', d)]
        # If no numbers, sort alphabetically after numbered items
        if not nums:
            return (1, [999999], d.lower())
        return (0, nums, d.lower())
    for track_name in tracks:
        tracks[track_name].sort(key=_sort_key)
    # Reorder tracks according to saved order
    ordered_tracks = {}
    for t in track_order:
        if t in tracks:
            ordered_tracks[t] = tracks.pop(t)
    # Add any remaining tracks not in saved order
    for t in sorted(tracks.keys()):
        ordered_tracks[t] = tracks[t]
    # Serialize plans for JS (horizontal timeline needs JSON)
    plans_json = [{
        "id": p.id, "title": p.title, "description": p.description,
        "status": p.status, "track": p.track, "event_type": p.event_type,
        "story_date": p.story_date, "sort_order": p.sort_order,
    } for p in plans]
    return render_template("plans/timeline.html", plans=plans, plans_json=plans_json,
                           tracks=ordered_tracks,
                           active_nav="plans_timeline")


@bp.route("/timeline/reorder", methods=["POST"])
def timeline_reorder():
    """Reorder timeline tracks. Payload: {tracks: ["Main Plot", "Subplot", ...]}"""
    data = request.get_json(silent=True) or {}
    track_names = data.get("tracks", [])
    try:
        plan_service.reorder_tracks(track_names)
        return jsonify({"ok": True})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


@bp.route("/corkboard")
def corkboard():
    """Scrivener-style corkboard: index cards for chapters + plan items."""
    from services import chapter_service
    chapters = chapter_service.list_chapters(sort="sort_order")[0]
    plans = plan_service.list_plans()
    return render_template("plans/corkboard.html",
                           chapters=chapters, plans=plans,
                           active_nav="plans_corkboard")


# ---- Subtasks ----

@bp.route("/<plan_id>/subtasks", methods=["POST"])
def add_subtask(plan_id: str):
    data = request.get_json(silent=True) or request.form
    title = data.get("title", "").strip()
    if not title:
        return jsonify({"ok": False, "error": "Title required"}), 400
    try:
        st = plan_service.add_subtask(plan_id, title)
        return jsonify({"ok": True, "id": st.id, "title": st.title})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


@bp.route("/subtasks/<subtask_id>/toggle", methods=["POST"])
def toggle_subtask(subtask_id: str):
    try:
        from sqlalchemy import select
        from core.db import read_session, write_transaction
        from models.plan import PlanSubtask
        with read_session() as s:
            st = s.get(PlanSubtask, subtask_id)
            current = bool(st.is_completed) if st else False
        plan_service.update_subtask(subtask_id, is_completed=not current)
        return jsonify({"ok": True, "completed": not current})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


@bp.route("/subtasks/<subtask_id>/edit", methods=["POST"])
def edit_subtask(subtask_id: str):
    """Inline-edit a subtask's title."""
    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()
    if not title:
        return jsonify({"ok": False, "error": "Title required"}), 400
    try:
        st = plan_service.update_subtask(subtask_id, title=title)
        return jsonify({"ok": True, "title": st.title})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


@bp.route("/subtasks/<subtask_id>/delete", methods=["POST"])
def delete_subtask(subtask_id: str):
    try:
        plan_service.delete_subtask(subtask_id)
        return jsonify({"ok": True})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


@bp.route("/<plan_id>/subtasks/reorder", methods=["POST"])
def reorder_subtasks(plan_id: str):
    data = request.get_json(silent=True) or {}
    ordered_ids = data.get("order", [])
    try:
        plan_service.reorder_subtasks(plan_id, ordered_ids)
        return jsonify({"ok": True})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code
