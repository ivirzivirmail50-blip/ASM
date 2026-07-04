"""Settings routes — appearance, story metadata, goals, AI (opt-in)."""
from __future__ import annotations

import json
import logging

from flask import (Blueprint, jsonify, render_template, request, url_for)

from core.db import read_session, write_transaction
from core.errors import AsmError
from models.settings import Setting, DEFAULT_SETTINGS
from services import validate_service, backup_service
from services._common import current_project_id

log = logging.getLogger("asm.routes.settings")
bp = Blueprint("settings", __name__, url_prefix="/settings")


@bp.route("/")
def index():
    with read_session() as s:
        settings = Setting.all_settings(s)
    return render_template("settings.html", settings=settings,
                           active_nav="settings")


@bp.route("/save", methods=["POST"])
def save():
    data = request.get_json(silent=True) or request.form
    # Coerce types from form strings.
    bool_keys = {"auto_backup_enabled", "sidebar_collapsed"}
    int_keys = {"daily_word_goal", "total_word_goal",
                "manuscript_font_size", "autosave_interval_seconds",
                "version_snapshot_interval_minutes", "auto_backup_interval_hours",
                "editor_font_size", "chapter_viewer_font_size",
                "ai.timeout_seconds"}
    try:
        with write_transaction() as s:
            for k, v in data.items():
                if k in bool_keys:
                    Setting.set(s, k, bool(v in (True, "true", "1", "on")))
                elif k in int_keys:
                    try:
                        Setting.set(s, k, int(v))
                    except (ValueError, TypeError):
                        pass
                elif k == "ai.enabled":
                    Setting.set(s, "ai.enabled", bool(v in (True, "true", "1", "on")))
                elif k.startswith("ai."):
                    Setting.set(s, k, str(v) if v is not None else "")
                else:
                    Setting.set(s, k, str(v) if v is not None else "")
        return jsonify({"ok": True})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


@bp.route("/ai")
def ai_settings():
    with read_session() as s:
        settings = Setting.all_settings(s)
    # Never expose ai.api_key in templates
    settings["ai.api_key"] = "" if not settings.get("ai.api_key") else "********"
    return render_template("settings_ai.html", settings=settings,
                           active_nav="settings")


@bp.route("/ai/test", methods=["POST"])
def ai_test():
    """Quick smoke test: try a tiny generate() call."""
    from services import ai_service
    try:
        out = ai_service.generate("Hello.", max_tokens=10)
        return jsonify({"ok": True, "response": out})
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


@bp.route("/validate")
def validate():
    result = validate_service.validate_all()
    return render_template("settings_validate.html", result=result,
                           active_nav="settings")


@bp.route("/validate/fix-word-counts", methods=["POST"])
def validate_fix_wc():
    fixed = validate_service.fix_word_counts()
    return jsonify({"ok": True, "fixed": fixed})


@bp.route("/backup", methods=["GET", "POST"])
def backup():
    if request.method == "POST":
        try:
            path = backup_service.create_backup()
            return jsonify({"ok": True, "name": path.name})
        except Exception as exc:
            return jsonify({"ok": False, "error": str(exc)}), 500
    backups = backup_service.list_backups()
    return render_template("settings_backup.html", backups=backups,
                           active_nav="settings")


@bp.route("/backup/restore", methods=["POST"])
def backup_restore():
    path = (request.get_json(silent=True) or {}).get("path")
    if not path:
        return jsonify({"ok": False, "error": "Missing path"}), 400
    try:
        backup_service.restore_backup(path)
        return jsonify({"ok": True,
                        "message": "Restore successful. Restart the app."})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@bp.route("/export-json")
def export_json():
    """Export entire project as JSON."""
    from sqlalchemy import select
    from models.chapter import Chapter, ChapterVersion
    from models.character import (Character, CharacterArc, CharacterGroup,
                                   CharacterGroupMember, CharacterRelationship)
    from models.plan import Plan, PlanSubtask
    from models.world import WorldEntry, WorldEntryRelation, WorldEntryVersion
    data = {"version": "asm-v4", "settings": {}}
    with read_session() as s:
        data["settings"] = Setting.all_settings(s)
        # Strip API key
        data["settings"]["ai.api_key"] = ""
        pid = current_project_id(s)
        data["chapters"] = [_model_to_dict(c) for c in s.scalars(
            select(Chapter).where(Chapter.project_id == pid)
        ).all()]
        data["chapter_versions"] = [_model_to_dict(v) for v in s.scalars(
            select(ChapterVersion)
        ).all()]
        data["characters"] = [_model_to_dict(c) for c in s.scalars(
            select(Character).where(Character.project_id == pid)
        ).all()]
        data["character_groups"] = [_model_to_dict(g) for g in s.scalars(
            select(CharacterGroup).where(CharacterGroup.project_id == pid)
        ).all()]
        data["character_group_members"] = [_model_to_dict(gm) for gm in s.scalars(
            select(CharacterGroupMember)
        ).all()]
        data["character_relationships"] = [_model_to_dict(r) for r in s.scalars(
            select(CharacterRelationship)
        ).all()]
        data["character_arcs"] = [_model_to_dict(a) for a in s.scalars(
            select(CharacterArc)
        ).all()]
        data["plans"] = [_model_to_dict(p) for p in s.scalars(
            select(Plan).where(Plan.project_id == pid)
        ).all()]
        data["plan_subtasks"] = [_model_to_dict(s2) for s2 in s.scalars(
            select(PlanSubtask)
        ).all()]
        data["world_entries"] = [_model_to_dict(w) for w in s.scalars(
            select(WorldEntry).where(WorldEntry.project_id == pid)
        ).all()]
        data["world_entry_versions"] = [_model_to_dict(v) for v in s.scalars(
            select(WorldEntryVersion)
        ).all()]
        data["world_relations"] = [_model_to_dict(r) for r in s.scalars(
            select(WorldEntryRelation)
        ).all()]
    from flask import Response
    return Response(json.dumps(data, ensure_ascii=False, indent=2,
                                default=str),
                    mimetype="application/json",
                    headers={"Content-Disposition":
                             "attachment; filename=asm_project.json"})


@bp.route("/import-json", methods=["GET", "POST"])
def import_json():
    """Import project from JSON. POST with file upload."""
    if request.method == "POST":
        if "file" not in request.files:
            return jsonify({"ok": False, "error": "No file provided"}), 400
        f = request.files["file"]
        if not f.filename:
            return jsonify({"ok": False, "error": "Empty filename"}), 400
        try:
            content = f.read().decode("utf-8")
            data = json.loads(content)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            return jsonify({"ok": False, "error": f"Invalid JSON: {exc}"}), 400
        try:
            result = _import_project_data(data)
            return jsonify({"ok": True, **result})
        except Exception as exc:
            log.exception("Import failed")
            return jsonify({"ok": False, "error": str(exc)}), 500
    # GET: render import form
    return render_template("settings_import.html", active_nav="settings")


def _import_project_data(data: dict) -> dict:
    """Import project data from a dict. Returns counts of imported entities."""
    from datetime import datetime
    from models.chapter import Chapter, ChapterVersion
    from models.character import (Character, CharacterArc, CharacterGroup,
                                   CharacterGroupMember, CharacterRelationship)
    from models.plan import Plan, PlanSubtask
    from models.world import WorldEntry, WorldEntryRelation, WorldEntryVersion
    from models.project import Project
    counts = {}

    def _parse_dt(v):
        if not v:
            return None
        try:
            return datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return None

    with write_transaction() as s:
        # Settings (skip ai.api_key for security unless explicitly present)
        if "settings" in data:
            for k, v in data["settings"].items():
                if k == "ai.api_key" and not v:
                    continue  # don't blank the key
                Setting.set(s, k, v)
        # Project
        if "project" in data:
            proj = data["project"]
            if not s.get(Project, proj.get("id", "default")):
                s.add(Project(
                    id=proj.get("id", "default"),
                    name=proj.get("name", "Imported Story"),
                    subtitle=proj.get("subtitle"),
                ))
        # Chapters
        for ch_data in data.get("chapters", []):
            cid = ch_data["id"]
            if not s.get(Chapter, cid):
                s.add(Chapter(
                    id=cid, project_id=ch_data.get("project_id", "default"),
                    title=ch_data["title"], content=ch_data.get("content", ""),
                    synopsis=ch_data.get("synopsis"), status=ch_data.get("status", "draft"),
                    word_count=ch_data.get("word_count", 0),
                    target_word_count=ch_data.get("target_word_count"),
                    sort_order=ch_data.get("sort_order", 0),
                    character_ids=ch_data.get("character_ids", "[]"),
                    tags=ch_data.get("tags", "[]"),
                    raw_file_path=ch_data.get("raw_file_path"),
                    created_at=_parse_dt(ch_data.get("created_at")) or datetime.now(),
                    updated_at=_parse_dt(ch_data.get("updated_at")) or datetime.now(),
                ))
        counts["chapters"] = len(data.get("chapters", []))
        # Chapter versions
        for v in data.get("chapter_versions", []):
            if not s.get(ChapterVersion, v["id"]):
                s.add(ChapterVersion(
                    id=v["id"], chapter_id=v["chapter_id"],
                    version_number=v["version_number"], content=v.get("content", ""),
                    word_count=v.get("word_count", 0), source=v.get("source", "manual"),
                    uploaded_at=_parse_dt(v.get("uploaded_at")) or datetime.now(),
                    notes=v.get("notes"),
                ))
        counts["chapter_versions"] = len(data.get("chapter_versions", []))
        # Characters
        for c in data.get("characters", []):
            if not s.get(Character, c["id"]):
                s.add(Character(
                    id=c["id"], project_id=c.get("project_id", "default"),
                    name=c["name"], role=c.get("role", "supporting"),
                    age=c.get("age"), gender=c.get("gender"),
                    aliases=c.get("aliases", "[]"),
                    avatar_color=c.get("avatar_color"),
                    avatar_path=c.get("avatar_path"),
                    physical=c.get("physical"), psychology=c.get("psychology"),
                    background=c.get("background"), philosophy=c.get("philosophy"),
                    philosophy_quotes=c.get("philosophy_quotes", "[]"),
                    story_role=c.get("story_role"),
                    story_role_chapters=c.get("story_role_chapters", "[]"),
                    voice=c.get("voice"), notes=c.get("notes"),
                    graph_x=c.get("graph_x"), graph_y=c.get("graph_y"),
                    created_at=_parse_dt(c.get("created_at")) or datetime.now(),
                    updated_at=_parse_dt(c.get("updated_at")) or datetime.now(),
                ))
        counts["characters"] = len(data.get("characters", []))
        # Character groups
        for g in data.get("character_groups", []):
            if not s.get(CharacterGroup, g["id"]):
                s.add(CharacterGroup(
                    id=g["id"], project_id=g.get("project_id", "default"),
                    name=g["name"], description=g.get("description"),
                    color=g.get("color", "#6366f1"),
                ))
        # Group members
        for gm in data.get("character_group_members", []):
            if not s.get(CharacterGroupMember, gm["id"]):
                s.add(CharacterGroupMember(
                    id=gm["id"], character_id=gm["character_id"],
                    group_id=gm["group_id"],
                ))
        # Relationships
        for r in data.get("character_relationships", []):
            if not s.get(CharacterRelationship, r["id"]):
                s.add(CharacterRelationship(
                    id=r["id"], from_character_id=r["from_character_id"],
                    to_character_id=r["to_character_id"],
                    relationship_type=r["relationship_type"],
                    description=r.get("description"),
                    is_bidirectional=r.get("is_bidirectional", False),
                    created_at=_parse_dt(r.get("created_at")) or datetime.now(),
                ))
        # Arcs
        for a in data.get("character_arcs", []):
            if not s.get(CharacterArc, a["id"]):
                s.add(CharacterArc(
                    id=a["id"], character_id=a["character_id"],
                    arc_name=a["arc_name"], description=a.get("description"),
                    stages=a.get("stages", "[]"),
                    created_at=_parse_dt(a.get("created_at")) or datetime.now(),
                ))
        # Plans
        from datetime import date as date_type
        for p in data.get("plans", []):
            if not s.get(Plan, p["id"]):
                deadline = None
                if p.get("deadline"):
                    try:
                        deadline = date_type.fromisoformat(p["deadline"])
                    except (ValueError, TypeError):
                        pass
                s.add(Plan(
                    id=p["id"], project_id=p.get("project_id", "default"),
                    title=p["title"], description=p.get("description"),
                    status=p.get("status", "idea"), column=p.get("column", "idea"),
                    sort_order=p.get("sort_order", 0),
                    chapter_id=p.get("chapter_id"), parent_id=p.get("parent_id"),
                    depends_on_id=p.get("depends_on_id"),
                    story_date=p.get("story_date"), event_type=p.get("event_type"),
                    track=p.get("track"),
                    characters_involved=p.get("characters_involved", "[]"),
                    deadline=deadline, effort_estimate=p.get("effort_estimate"),
                    tags=p.get("tags", "[]"),
                    created_at=_parse_dt(p.get("created_at")) or datetime.now(),
                    updated_at=_parse_dt(p.get("updated_at")) or datetime.now(),
                ))
        counts["plans"] = len(data.get("plans", []))
        # Subtasks
        for st in data.get("plan_subtasks", []):
            if not s.get(PlanSubtask, st["id"]):
                s.add(PlanSubtask(
                    id=st["id"], plan_id=st["plan_id"], title=st["title"],
                    is_completed=st.get("is_completed", False),
                    sort_order=st.get("sort_order", 0),
                    created_at=_parse_dt(st.get("created_at")) or datetime.now(),
                ))
        # World entries
        for e in data.get("world_entries", []):
            if not s.get(WorldEntry, e["id"]):
                s.add(WorldEntry(
                    id=e["id"], project_id=e.get("project_id", "default"),
                    type=e["type"], name=e["name"], category=e.get("category"),
                    description=e.get("description"), content=e.get("content"),
                    notes=e.get("notes"), metadata_=e.get("metadata", "{}"),
                    parent_id=e.get("parent_id"),
                    map_pin_x=e.get("map_pin_x"), map_pin_y=e.get("map_pin_y"),
                    map_pin_label=e.get("map_pin_label"),
                    map_image_path=e.get("map_image_path"),
                    sort_order=e.get("sort_order", 0),
                    created_at=_parse_dt(e.get("created_at")) or datetime.now(),
                    updated_at=_parse_dt(e.get("updated_at")) or datetime.now(),
                ))
        counts["world_entries"] = len(data.get("world_entries", []))
        # World versions
        for v in data.get("world_entry_versions", []):
            if not s.get(WorldEntryVersion, v["id"]):
                s.add(WorldEntryVersion(
                    id=v["id"], entry_id=v["entry_id"],
                    version_number=v["version_number"],
                    snapshot=v.get("snapshot", "{}"), source=v.get("source", "manual"),
                    created_at=_parse_dt(v.get("created_at")) or datetime.now(),
                    notes=v.get("notes"),
                ))
        # World relations
        for r in data.get("world_relations", []):
            if not s.get(WorldEntryRelation, r["id"]):
                s.add(WorldEntryRelation(
                    id=r["id"], from_entry_id=r["from_entry_id"],
                    to_entry_id=r["to_entry_id"],
                    relation_type=r["relation_type"],
                    description=r.get("description"),
                ))
    return counts


@bp.route("/world-types", methods=["POST"])
def manage_world_types():
    """Add or remove custom world entry types."""
    data = request.get_json(silent=True) or request.form
    action = data.get("action")
    name = data.get("name", "").strip()
    try:
        from services import world_service
        if action == "add":
            types = world_service.add_custom_type(name)
            return jsonify({"ok": True, "types": types})
        elif action == "remove":
            types = world_service.remove_custom_type(name)
            return jsonify({"ok": True, "types": types})
        else:
            return jsonify({"ok": False, "error": "Unknown action"}), 400
    except AsmError as exc:
        return jsonify({"ok": False, "error": exc.user_message}), exc.status_code


def _model_to_dict(obj) -> dict:
    """Convert a SQLAlchemy model to a dict using its column names."""
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}
